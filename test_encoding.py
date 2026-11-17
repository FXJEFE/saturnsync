# -*- coding: utf-8 -*-
import json
import os
import logging

from fxjefe_paths import load_config, require_root
config = {}
import pandas as pd
import os

files = [
    'log.txt',
    'FXJEFE_Features.csv',
    'FXJEFE_trades_outcomes.csv',
    'FXJEFE_trades.csv'
]

from fxjefe_paths import mql5_subdir
base_dir = str(mql5_subdir("Files"))

for file in files:
    try:
        if file.endswith('.csv'):
            df = pd.read_csv(os.path.join(base_dir, file), encoding='utf-8')
            print(f'Successfully read {file} as UTF-8')
        else:
            with open(os.path.join(base_dir, file), 'r', encoding='utf-8') as f:
                content = f.read()
            print(f'Successfully read {file} as UTF-8')
    except Exception as e:
        print(f'Error reading {file}: {str(e)}')