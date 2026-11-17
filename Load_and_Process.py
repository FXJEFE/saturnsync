"""
Load_and_Process.py
Loads FXJEFE_Features.csv, validates the 27 model feature columns are present,
reports basic statistics, and exits.  Run standalone or via pipeline for a
quick data-quality check before training.
"""
import os
import logging
import pandas as pd

config = {}


def main():
    expected_columns = ['time', 'symbol', 'price'] + [
        c for c in config['features'] if c != 'price'
    ] + ['signal']
    input_path = os.path.join(config['data_path'], 'FXJEFE_Features.csv')

    if not os.path.exists(input_path):
        logging.error(f"Input file not found: {input_path}")
        logging.error("Run mt5_data_sync.py (or GenerateFeatures.mq5) first.")
        return 1

    df = pd.read_csv(input_path, encoding='utf-8-sig', low_memory=False)
    logging.info(f"Loaded {len(df)} rows, {len(df.columns)} columns.")
    logging.info(f"Columns present: {list(df.columns)}")

    missing = [c for c in expected_columns if c not in df.columns]
    if missing:
        logging.warning(f"Missing expected columns: {missing}")
    else:
        logging.info("All expected columns present.")

    numeric_cols = [c for c in config['features'] if c in df.columns]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    null_counts = df[numeric_cols].isnull().sum()
    if null_counts.any():
        logging.warning(f"NaN counts per feature:\n{null_counts[null_counts > 0].to_string()}")
    else:
        logging.info("No NaN values found in feature columns.")

    logging.info(f"Row count: {len(df)}")
    if len(df) < 500:
        logging.warning("Less than 500 rows — re-run GenerateFeatures.mq5 with more History_Bars.")

    if 'symbol' in df.columns:
        logging.info(f"Symbols: {df['symbol'].unique().tolist()}")

    logging.info("Load_and_Process completed successfully.")
    return 0


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    global config
    ctx = activate("Load_and_Process.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    return main()


if __name__ == '__main__':
    import sys
    from stage_support import call_main
    sys.exit(call_main(run))
