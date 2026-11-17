# FXJEFE

Production ML + MetaTrader 5 trading runtime.

**Policy:** UTF-8 only · all features permitted · no filtering / labeling / blocking of feature names · signals only when model is loaded and featureset matches EA + server + Predict.mq5 + GenerateFeatures.mq5.

The pipeline entry point in this repo is `run_pipeline.py`. It starts every stage in dependency order. **Live trading is the default.** `run_pipeline.bat` places real orders without `--live`. Use `--paper` (or `--dry-run`) for a test run. `--live` is accepted and does not change the default.

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

`setup_windows.bat` calls `setup_windows.ps1`. It installs Python 3.11.9 and Python 3.8.10 (64-bit, per-user) when those launchers are missing, then creates `<PROJECT_ROOT>\fxjefe` (3.11, `requirements.txt`) and `<PROJECT_ROOT>\fxjefe38` (3.8.10, `requirements-fxjefe38.txt`, plus the TA-Lib 0.4.28 cp38 Windows wheel).

`run_pipeline.bat` runs `run_pipeline.py` with the `fxjefe` interpreter in **LIVE MODE**. Feature engineering, `full_pipeline.py`, and the LSTM stage use `fxjefe38` when that venv exists. Startup prints `LIVE MODE` and refuses to start unless `configftmo.json` is in `PROJECT_ROOT` and `MT5_ACCOUNT`, `MT5_PASSWORD`, and `MT5_SERVER` are set. The FTMO gate (6.66% drawdown stop on new entries, 11.1% profit target stop, no auto-close), the margin guard (level at least 300, free margin never negative), the feature-hash match, and the MT5 health check still have to pass before an order. For a test run: `run_pipeline.bat --paper`.

Override the root before either command:

```bat
set FXJEFE_PROJECT_DIR=D:\FXJEFE_Project
setup_windows.bat
run_pipeline.bat
```

Broker login is read from `MT5_ACCOUNT`, `MT5_PASSWORD`, and `MT5_SERVER`. None of those values are stored in the repo.

## FTMO rules

The primary rules file is `PROJECT_ROOT\configftmo.json`. `configftmo.example.json` is checked in with the demo-200k rules: max drawdown 6.66 percent (new entries stop, open positions stay open), per-trade risk 33.3 percent, profit target 11.1 percent, max position size 1.0, max leverage 100, and a margin-level floor of 300. Older `ftmo_config` / `FTMOConfig` filenames and `_pct` aliases still load. `FXJEFE_MQL5_DIR` overrides `mt5_mql5_dir`. The risk gate runs before `process_trades.py`. `--paper` never calls `order_send`. Live mode calls it only after the gate passes.

Verify with `fxjefe\Scripts\python.exe run_pipeline.py --verify`. If `checksums.json` is missing, `python verify_checksums.py --write` creates it and says so when it is absent.

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

Use `setup_windows.bat`. That creates `fxjefe` (Python 3.11.9) and `fxjefe38` (Python 3.8.10).

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
