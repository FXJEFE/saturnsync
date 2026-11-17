# FXJEFE

Production ML + MetaTrader 5 trading runtime.

**Policy:** UTF-8 only · all features permitted · no filtering / labeling / blocking of feature names · signals only when model is loaded and featureset matches EA + server + Predict.mq5 + GenerateFeatures.mq5.

The pipeline entry point in this repo is `run_pipeline.py`. It starts every stage in dependency order and stays in paper mode unless you pass `--live`.

---

## Project root

One setting, `PROJECT_ROOT`, is used by `run_pipeline.py` and every stage:

1. `--project-dir`
2. environment variable `FXJEFE_PROJECT_DIR`
3. `Path.home() / "Documents" / "FXJEFE_Project"`

On Windows that default is `C:\Users\<you>\Documents\FXJEFE_Project`. Startup logs `PROJECT_ROOT=...` and exits if that directory does not exist. Data, model, log, and `config.json` paths are resolved under it.

```text
~/Documents/FXJEFE_Project
Windows: %USERPROFILE%\Documents\FXJEFE_Project
```

## Windows setup and run (Python 3.8.10 x64)

Clone this repo into the project root, then:

```bat
setup_windows.bat
run_pipeline.bat
```

`setup_windows.bat` calls `setup_windows.ps1`. If `py -3.8` is missing it downloads the official Python 3.8.10 64-bit installer from python.org and installs it for the current user. It then creates `<PROJECT_ROOT>\.venv` and pip-installs `requirements.txt` (versions pinned for CPython 3.8.10 on 64-bit Windows, including MetaTrader5).

`run_pipeline.bat` activates that virtualenv and runs `run_pipeline.py` from `PROJECT_ROOT` in paper mode. Add `--live` only when a real FTMO rules file is in place and you intend to allow `order_send` after the risk gate.

Override the root before either command:

```bat
set FXJEFE_PROJECT_DIR=D:\FXJEFE_Project
setup_windows.bat
run_pipeline.bat
```

Broker login is read from `MT5_ACCOUNT`, `MT5_PASSWORD`, and `MT5_SERVER`. None of those values are stored in the repo.

## FTMO rules

No FTMO config file was found in this repo, in `FXJEFE/user_documents_fxjefe_project`, or in the other FXJEFE trees this account can read. `FXJEFE/BalalaikaBandits` is not accessible (HTTP 404). The pipeline does not invent daily-loss or drawdown numbers. Put the real rules at `PROJECT_ROOT\ftmo_config.json` (or set `FTMO_CONFIG`). Until that file contains recognized limits, `ftmo_rules.py` fails and no later stage runs. The risk gate in `risk_management.py` runs again before `process_trades.py` and is the only place an order is allowed to proceed. Paper mode never calls `order_send`.

## Stage order

`run_pipeline.py` calls each script's `run()`:

1. Project root, `path_validate.py`, `validate_config.py`, `ftmo_rules.py`
2. `mt5_health.py`
3. Data: `mt5_data_sync.py`, `mt5_generate_features.py`, `mt5_generate_crypto_features.py`, `validate_data.py`, `Load_and_Process.py`, `fix_csv.py`, `fix_csv_encoding.py`, `adjust_headers.py`, `convert_encoding.py`
4. Features: `generate_training_data.py`, `generate_labels.py`, `generate_new_csv.py`, `clean_training_data.py`
5. Model: `train_models.py`, `feature_engineering.py`, `check_model_features.py`, `full_pipeline.py`, `model_deploy.py`
6. Signals: `ensemble_predictions.py`, `generate_signals_with_xgboost.py`, `get_lstm_prediction.py`, `signal_processor.py`, `signal_gate.py`, `mt5_signal_script.py`
7. FTMO gate: `risk_management.py`
8. Execution: `process_trades.py`
9. Monitoring: `merge_datasets.py`, `analyze_outcomes.py`, `update_database.py`, `check_integrity.py`, `check_labels.py`, `log_summary.py`

---

## Quick setup

### 1. Clone

```bash
mkdir -p ~/Documents
cd ~/Documents
git clone https://github.com/FXJEFE/saturnsync.git FXJEFE_Project
cd FXJEFE_Project
```

### 2. Python venv

**macOS**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements_mac.txt
```

**Linux**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements_linux.txt
```

**Windows (PowerShell)**

Use `setup_windows.bat` (Python 3.8.10 and `<PROJECT_ROOT>\.venv`). Do not create a 3.11 virtualenv for the MT5 pipeline.

### 3. Environment

```bash
cp .env.example .env
```

Edit `.env` with MT5 account values locally. Never commit `.env`.

### 4. Lock runtime (expect 200)

```bash
python runtime_lock.py
```

### 5. Feature hash + signal gate smoke test

```bash
python feature_hash.py
python signal_gate.py
```

### 6. Production pipeline (optional)

```bash
python pipelinerun_production.py
```

After first green FINAL:

```bash
python secure_strap.py
```

---

## Feature policy (ALL OK)

| Rule | Value |
|------|--------|
| `feature_policy` | `ACCEPT_ALL_FEATURES` |
| Filter / block / refuse feature names | **Never** |
| Strip feature arrays | **Never** |
| Preferred 17 / 28 lists | Defaults for wiring only |
| Signal emit | Model loaded **and** featureset hash matches EA + server + Predict.mq5 + GenerateFeatures.mq5 |

---

## Encoding

UTF-8 only for `.py`, `.csv`, `.mq5`, `.mqh`, `.json`, configs.

```bash
python encoding_utf8.py --fix
python encoding_utf8.py --scan
```

---

## MT5

Live terminals (Pepperstone / Vantage / FTMO) run on **Windows** (native or VM).  
Mac/Linux: training, feature engineering, AI server.  
EA: allow WebRequest for `http://127.0.0.1:8080` (and LAN IP if split hosts).

---

## Do not commit

- `.env` (secrets)
- `venv/`
- `__pycache__/`
- `*.pkl` model binaries unless intentional
- live broker passwords

See `.gitignore`.
