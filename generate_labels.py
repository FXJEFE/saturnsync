"""
generate_labels.py
Reads FXJEFE_Features.csv (all 27 model features + price), fills gaps,
recomputes sentiment, adds price-change labels (1=buy, 0=hold, -1=sell),
and writes:
  data/FXJEFE_Features_fixed.csv
  data/FXJEFE_Features_with_labels.csv
  data/training_data.csv   ← consumed by train_models.py
"""
import os
import logging
import numpy as np
import pandas as pd

config = {}

# 27 model features (matches config['features'] after removing 'price')
MODEL_FEATURES = [
    'atr', 'ema_diff', 'rsi', 'macd_diff', 'vwap', 'price_vwap_diff',
    'bb_position', 'roc', 'stochastic', 'cci', 'williams', 'momentum',
    'realized_vol', 'chaikin_vol', 'adx', 'rvi', 'obv', 'volume_delta',
    'ad_line', 'vol_osc', 'supertrend', 'hma', 'ichimoku_tenkan', 'sar',
    'dpo', 'spread', 'sentiment'
]

FEATURE_DEFAULTS = {
    'atr': 0.0001, 'ema_diff': 0.0, 'rsi': 50.0, 'macd_diff': 0.0,
    'price_vwap_diff': 0.0, 'bb_position': 0.5, 'roc': 0.0, 'stochastic': 50.0,
    'cci': 0.0, 'williams': -50.0, 'momentum': 0.0,
    'realized_vol': 0.0, 'chaikin_vol': 0.0, 'adx': 25.0, 'rvi': 0.0,
    'obv': 0.0, 'volume_delta': 0.0, 'ad_line': 0.0, 'vol_osc': 0.0,
    'supertrend': 0.0, 'dpo': 0.0, 'spread': 2.0, 'sentiment': 0.0,
    # Price-derived — filled dynamically below
    'vwap': None, 'hma': None, 'ichimoku_tenkan': None, 'sar': None,
}

SENTIMENT_MAP = {
    "EURUSD": "Bullish trend expected",
    "USDJPY": "Neutral market",
    "XAUUSD": "Bearish sentiment",
    "AUDUSD": "Positive outlook",
    "GBPUSD": "Strong buy signals",
    "USDCAD": "Sell pressure",
    "BTCUSD": "Volatile bullish momentum",
    "XRPUSD": "Speculative neutral",
}

_SENTIMENT_CACHE = {}


def get_sentiment(symbol):
    key = str(symbol).replace(".r", "").replace(".R", "").strip()
    if key in _SENTIMENT_CACHE:
        return _SENTIMENT_CACHE[key]
    text = SENTIMENT_MAP.get(key, "Neutral")
    try:
        from textblob import TextBlob
        value = TextBlob(text).sentiment.polarity
    except Exception:
        value = 0.0
    _SENTIMENT_CACHE[key] = value
    return value

def generate_labels(df):
    df = df.copy()
    look_ahead = config.get('look_ahead', 5)
    crypto_threshold = config.get('crypto_label_threshold', 0.002)
    forex_threshold  = config.get('forex_label_threshold', 0.001)
    crypto_symbols   = config.get('crypto_symbols', [])

    logging.info(f"look_ahead={look_ahead}, forex_threshold={forex_threshold}, crypto_threshold={crypto_threshold}")

    df['future_price'] = df.groupby('symbol')['price'].shift(-look_ahead)
    df['price_change'] = (df['future_price'] - df['price']) / df['price']

    # Per-symbol threshold: wider for crypto, tighter for forex
    df['_threshold'] = df['symbol'].apply(
        lambda s: crypto_threshold if str(s).replace('.r','') in crypto_symbols else forex_threshold
    )
    df['label'] = np.select(
        [df['price_change'] > df['_threshold'], df['price_change'] < -df['_threshold']],
        [1, -1],
        default=0
    )
    df.drop(columns=['_threshold'], inplace=True)
    df = df.dropna(subset=['future_price', 'price_change'])

    for sym in df['symbol'].unique():
        dist = df[df['symbol'] == sym]['label'].value_counts().to_dict()
        logging.info(f"  {sym} labels: {dist}")
    logging.info(f"Overall label distribution: {df['label'].value_counts().to_dict()}")
    return df

def main():
    input_path    = os.path.join(config['data_path'],        'FXJEFE_Features.csv')
    fixed_path    = os.path.join(config['data_output_path'], 'FXJEFE_Features_fixed.csv')
    labeled_path  = os.path.join(config['data_output_path'], 'FXJEFE_Features_with_labels.csv')
    training_path = os.path.join(config['data_output_path'], 'training_data.csv')

    if not os.path.exists(input_path):
        logging.error(f"Input file not found: {input_path}")
        logging.error("Run mt5_data_sync.py (or GenerateFeatures.mq5) first.")
        return 1

    df = pd.read_csv(input_path, encoding='utf-8-sig', low_memory=False)
    logging.info(f"Read {len(df)} rows.  Columns: {list(df.columns)}")

    # Ensure all expected columns exist, including any config feature such as garch_vol.
    all_cols = ['time', 'symbol', 'price'] + MODEL_FEATURES + list(config.get('features') or []) + ['signal']
    for col in all_cols:
        if col not in df.columns:
            df[col] = '' if col in ('time', 'symbol', 'signal') else 0.0
            logging.info(f"Added missing column: {col}")

    df['price'] = pd.to_numeric(df['price'], errors='coerce').ffill()

    # Fill NaNs in features
    for col in MODEL_FEATURES:
        default = FEATURE_DEFAULTS.get(col)
        if default is None:          # price-derived
            default = df['price']
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(default)

    # Always recompute sentiment from symbol map
    df['sentiment'] = df['symbol'].apply(get_sentiment)

    nan_after = df[['price'] + MODEL_FEATURES].isna().sum()
    if nan_after.any():
        logging.warning(f"Remaining NaNs:\n{nan_after[nan_after > 0]}")
    if len(df) < 500:
        logging.warning(f"Only {len(df)} rows — re-run GenerateFeatures.mq5 with more History_Bars.")

    df.to_csv(fixed_path, encoding='utf-8', index=False)
    logging.info(f"Saved cleaned CSV  → {fixed_path}")

    df = generate_labels(df)
    df.to_csv(labeled_path, encoding='utf-8', index=False)
    logging.info(f"Saved labeled CSV  → {labeled_path}")

    # training_data.csv — only features + label for train_models.py
    train_cols = config['features'] + ['label']
    missing = [c for c in train_cols if c not in df.columns]
    if missing:
        logging.error(f"Missing training columns: {missing}")
        return 1
    df[train_cols].dropna().to_csv(training_path, encoding='utf-8', index=False)
    logging.info(f"Saved training CSV → {training_path}  ({len(df)} rows)")
    return 0


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    global config
    ctx = activate("generate_labels.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    return main()


if __name__ == '__main__':
    import sys
    from stage_support import call_main
    sys.exit(call_main(run))
