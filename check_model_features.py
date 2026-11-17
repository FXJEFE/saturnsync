"""
check_model_features.py
Loads my_model.pkl and verifies the number of features matches config.
"""
import os
import logging

config = {}


def main():
    import joblib

    model_path = os.path.join(config['models_path'], 'my_model.pkl')

    if not os.path.exists(model_path):
        logging.error(f"Model not found: {model_path}")
        logging.error("Run train_models.py first.")
        return 1

    model = joblib.load(model_path)
    n_model    = model.n_features_in_
    n_config   = len(config['features'])
    status     = "OK" if n_model == n_config else "MISMATCH"

    logging.info(f"Model feature count : {n_model}")
    logging.info(f"Config feature count: {n_config}  ({config['features']})")
    logging.info(f"Feature count check : {status}")

    if status != "OK":
        logging.error(
            "Feature count mismatch — model expects %s, config has %s.",
            n_model,
            n_config,
        )
        return 1
    return 0


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    global config
    ctx = activate("check_model_features.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    return main()


if __name__ == '__main__':
    import sys
    from stage_support import call_main
    sys.exit(call_main(run))
