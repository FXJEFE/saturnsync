"""
Deploy trained models (.onnx, .pkl, .json) to all configured MT5 terminals.
Copies from models/ to each terminal's MQL5/Files/ folder.
"""
import os
import shutil
from datetime import datetime

config = {}
MODELS_DIR = ""
EXTENSIONS = ['.onnx', '.json', '.pkl']

def deploy():
    terminals = list(config.get('mt5_terminals') or [])
    files_path = (config.get('mt5_files_path') or '').strip()
    if not terminals and files_path:
        terminals = [{'name': 'Default', 'files_path': files_path}]
    if not terminals:
        print("No MT5 files path configured; model files stay in %s" % MODELS_DIR)
        return 0

    model_files = [f for f in os.listdir(MODELS_DIR)
                   if any(f.endswith(ext) for ext in EXTENSIONS)]

    if not model_files:
        print("No model files found to deploy.")
        print("  Looked in: %s" % MODELS_DIR)
        print("  Extensions: %s" % EXTENSIONS)
        return 0

    print(f"Found {len(model_files)} model files to deploy:")
    for f in model_files:
        size = os.path.getsize(os.path.join(MODELS_DIR, f))
        print(f"  {f} ({size/1024:.0f} KB)")

    print()
    for terminal in terminals:
        name = terminal['name']
        dest = terminal['files_path']

        if not os.path.exists(dest):
            os.makedirs(dest, exist_ok=True)
            print(f"  Created: {dest}")

        print(f"Deploying to [{name}]: {dest}")
        for f in model_files:
            src = os.path.join(MODELS_DIR, f)
            dst = os.path.join(dest, f)
            shutil.copy2(src, dst)
            print(f"  Copied {f}")

        print(f"  Done ({len(model_files)} files)\n")

    # Also copy to Common files
    common = config.get('mt5_common_path', '')
    if common and os.path.exists(os.path.dirname(common)):
        os.makedirs(common, exist_ok=True)
        print(f"Deploying to [Common]: {common}")
        for f in model_files:
            shutil.copy2(os.path.join(MODELS_DIR, f), os.path.join(common, f))
            print(f"  Copied {f}")
        print()

    print("Deployment complete at %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return 0


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    global config, MODELS_DIR
    ctx = activate("model_deploy.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    MODELS_DIR = config["models_path"]
    if not os.path.isdir(MODELS_DIR):
        print("Models directory missing: %s" % MODELS_DIR)
        return 1
    return deploy() or 0


if __name__ == '__main__':
    import sys
    from stage_support import call_main
    sys.exit(call_main(run))
