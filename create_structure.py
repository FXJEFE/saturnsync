# -*- coding: utf-8 -*-
import json
import os
import logging

from fxjefe_paths import data_dir, project_root

# Load the config file safely
root_dir = str(data_dir(project_root()))

structure = {
    "config.json": None,
    "models": {
        "xgboost_model.json": None,
        "ensemble_model.pkl": None,
        "lightgbm_model.txt": None,
        "lstm_model.h5": None
    },
    "data": {
        "ai_server.log": None,
        "FXJEFE_Features.csv": None,
        "FXJEFE_Features.lock": None
    },
    "server.py": None,
    "risk_management.py": None,
    "logging_utils.py": None,
    "FXJEFElogtxt.txt": None,
    "FXJEFE_EA_AI_API_5.0.mq5": None,
    "GenerateFeatures.mq5": None,
    "Predict.mq5": None
}

def create_structure(base_path, structure):
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    for name, content in structure.items():
        path = os.path.join(base_path, name)
        if content is None:
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    pass
        else:
            if not os.path.exists(path):
                os.makedirs(path)
            create_structure(path, content)

if __name__ == "__main__":
    create_structure(root_dir, structure)
    print("Folder structure '%s' created successfully!" % root_dir)