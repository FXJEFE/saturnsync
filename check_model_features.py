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

    model = _load_model(model_path)
    n_model = _model_feature_count(model)
    from feature_hash import CONTRACT_FEATURES

    n_contract = len(CONTRACT_FEATURES)
    n_config = len(config['features'])
    logging.info("Model feature count : %s", n_model)
    logging.info("Contract feature count: %s", n_contract)
    logging.info("Config feature count: %s", n_config)
    if n_model != n_contract or n_config != n_contract:
        logging.error(
            "MODEL INPUT SIGNATURE FAIL: model has %s inputs, config lists %s, contract is the ordered %s-feature vector. A 28-input model does not match this contract.",
            n_model,
            n_config,
            n_contract,
        )
        return 1
    logging.info("Feature count check : OK")
    return 0


def _load_model(path):
    if str(path).lower().endswith(".onnx"):
        import onnxruntime

        return onnxruntime.InferenceSession(str(path))
    import joblib

    return joblib.load(path)


def _model_feature_count(model):
    if hasattr(model, "n_features_in_"):
        return int(model.n_features_in_)
    inputs = getattr(model, "get_inputs", None)
    if callable(inputs):
        shape = inputs()[0].shape
        if shape and shape[-1] not in (None, "None"):
            return int(shape[-1])
    raise RuntimeError("model does not expose an input signature")


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
