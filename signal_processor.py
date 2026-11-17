"""
signal_processor.py
Reads FXJEFE_Features.csv, applies SMA crossover logic to generate
buy/hold/sell signals per symbol, and writes signals_output.csv.
Supports --daemon for continuous operation; default is single-shot for pipeline use.
"""
import os
import logging
import time
import pandas as pd

config = {}
INPUT_PATH = ""
OUTPUT_PATH = ""


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['SMA_short'] = df.groupby('symbol')['price'].transform(
        lambda x: x.rolling(5,  min_periods=1).mean()
    )
    df['SMA_long'] = df.groupby('symbol')['price'].transform(
        lambda x: x.rolling(20, min_periods=1).mean()
    )
    df['signal'] = 'hold'
    df.loc[df['SMA_short'] > df['SMA_long'], 'signal'] = 'buy'
    df.loc[df['SMA_short'] < df['SMA_long'], 'signal'] = 'sell'
    return df


def process_once() -> bool:
    if not os.path.exists(INPUT_PATH):
        logging.warning(f"Input file not found: {INPUT_PATH} — run mt5_data_sync.py first.")
        return False

    df = pd.read_csv(INPUT_PATH, encoding='utf-8-sig', low_memory=False)
    if df.empty:
        logging.warning("Input CSV is empty.")
        return False

    df['price'] = pd.to_numeric(df['price'], errors='coerce').ffill()
    df = generate_signals(df)
    df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8')

    latest = df.groupby('symbol').last()[['price', 'signal']]
    logging.info(f"Signals written → {OUTPUT_PATH}\n{latest.to_string()}")
    return True


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    global config, INPUT_PATH, OUTPUT_PATH
    ctx = activate("signal_processor.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    INPUT_PATH = os.path.join(config['data_path'], 'FXJEFE_Features.csv')
    OUTPUT_PATH = os.path.join(config['data_output_path'], 'signals_output.csv')
    import sys
    if not dry_run and '--daemon' in sys.argv:
        logging.info("signal_processor daemon started")
        while True:
            try:
                process_once()
            except Exception as exc:
                logging.error("Error: %s", exc)
            time.sleep(60)
    try:
        return 0 if process_once() else 1
    except Exception as exc:
        logging.error("Error: %s", exc)
        return 1


if __name__ == '__main__':
    import sys
    from stage_support import call_main
    sys.exit(call_main(run))
