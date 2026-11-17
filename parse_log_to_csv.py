# -*- coding: utf-8 -*-
import json
import os
import logging

from fxjefe_paths import data_dir, load_config, logs_dir, project_root, require_root
config = {}
import pandas as pd
import re
import json
import logging
import os
from multiprocessing import Pool, cpu_count, freeze_support
import json

try:
    config = load_config(require_root())
except Exception:
    config = {"data_output_path": str(data_dir(project_root())), "log_path": str(logs_dir(project_root()))}

log_file = os.path.join(config['data_output_path'], 'log.txt')
output_csv = os.path.join(config['data_output_path'], 'FXJEFE_Features.csv')

# Setup logging
logging.basicConfig(level=logging.INFO, filename='parse_log.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

# File paths (adjusted for your folder)
_root = project_root()
LOG_PATH = str(logs_dir(_root) / "log.txt")
OUTPUT_PATH = str(data_dir(_root) / "FXJEFE_Features.csv")

# Regex patterns
api_pattern = re.compile(r"(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}).*Sending API request for (\w+\.r): ({.*})")
signal_pattern = re.compile(r"(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}).*Server response for (\w+\.r): .*\"signal\":\"(buy|sell|hold)\"")

# Try different encodings
encodings = ['utf-8', 'utf-16le', 'ansi', 'latin1']
log_lines = None
for enc in encodings:
    try:
        with open(LOG_PATH, "r", encoding=enc) as file:
            log_lines = file.readlines()
        logging.info(f"Successfully read log with {enc} encoding")
        break
    except (UnicodeDecodeError, OSError) as e:
        logging.error(f"Failed to decode with {enc}: {e}")
if log_lines is None:
    logging.error("All encodings failed or log.txt is missing. Check %s", LOG_PATH)
    log_lines = []

# Parse individual log lines
def parse_line(line):
    api_match = api_pattern.search(line)
    if api_match:
        time, symbol, json_data = api_match.groups()
        try:
            data = json.loads(json_data)
            return {
                "time": time,
                "symbol": symbol,
                "price": float(data["price"]),
                "atr": float(data["atr"]),
                "ema_diff": float(data["ema_diff"]),
                "rsi": float(data["rsi"]),
                "garch_vol": float(data["garch_vol"]),
                "macd_diff": float(data["macd_diff"]),
                "vwap": float(data["vwap"]),
                "price_vwap_diff": float(data["price_vwap_diff"]),
                "bb_position": float(data["bb_position"]),
                "signal": "hold",
                "future_return": float('nan'),  # Placeholder
                "threshold": float('nan'),      # Placeholder
                "label": 0                      # Placeholder
            }
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON for {symbol} at {time}: {json_data} - {e}")
            return None
    return None

def main():
    with Pool(cpu_count()) as pool:
        results = pool.map(parse_line, log_lines)
    trade_list = [r for r in results if r is not None]

    # Update signals
    for line in log_lines:
        signal_match = signal_pattern.search(line)
        if signal_match:
            time, symbol, signal = signal_match.groups()
            for trade in trade_list:
                if trade["time"] == time and trade["symbol"] == symbol:
                    trade["signal"] = signal
                    break

    # Create DataFrame with full header
    df = pd.DataFrame(trade_list).dropna(subset=["price"])
    if df.empty:
        logging.error("No valid trade data extracted.")
        exit(1)

    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S.%f")
    df = df.sort_values("time").reset_index(drop=True)
    df.to_csv(OUTPUT_PATH, index=False)
    logging.info(f"{OUTPUT_PATH} created with {len(df)} entries")

if __name__ == '__main__':
    freeze_support()
    main()