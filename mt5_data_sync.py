"""
mt5_data_sync.py
Copies FXJEFE_Features.csv from the MT5 Files folder into the project data folder.
MT5 writes the file via FILE_COMMON → Common/Files, and also to the terminal-specific
MQL5/Files folder.  This script checks both locations and uses whichever is newer.
"""
import os
import shutil
import time
import logging

config = {}
FILENAME = 'FXJEFE_Features.csv'
DEST_PATH = ''
SOURCE_CANDIDATES = []


def _bind(cfg):
    global config, DEST_PATH, SOURCE_CANDIDATES
    config = cfg
    DEST_PATH = os.path.join(config['data_path'], FILENAME)
    SOURCE_CANDIDATES = []
    for key in ('mt5_common_path', 'mt5_files_path'):
        folder = (config.get(key) or '').strip()
        if folder:
            SOURCE_CANDIDATES.append(os.path.join(folder, FILENAME))
    try:
        from fxjefe_paths import mql5_subdir
        SOURCE_CANDIDATES.append(os.path.join(str(mql5_subdir("Files")), FILENAME))
    except Exception:
        pass

def best_source():
    candidates = [(p, os.path.getmtime(p)) for p in SOURCE_CANDIDATES if os.path.exists(p)]
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[1])[0]

def sync_once():
    src = best_source()
    if src is None:
        logging.warning("FXJEFE_Features.csv not found in any MT5 folder. "
                        "Run GenerateFeatures.mq5 first.")
        return False
    src_mtime  = os.path.getmtime(src)
    dest_mtime = os.path.getmtime(DEST_PATH) if os.path.exists(DEST_PATH) else 0
    if src_mtime > dest_mtime:
        shutil.copy2(src, DEST_PATH)
        logging.info(f"Synced  {src}  →  {DEST_PATH}")
    else:
        logging.debug("No update needed (destination is current).")
    return True

def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate('mt5_data_sync.log', project_dir=project_dir, dry_run=dry_run)
    _bind(ctx['config'])
    import sys
    if not dry_run and '--daemon' in sys.argv:
        logging.info("mt5_data_sync daemon started.")
        while True:
            try:
                sync_once()
            except Exception as exc:
                logging.error("Sync error: %s", exc)
            time.sleep(60)
    try:
        sync_once()
    except Exception as exc:
        logging.error("Sync error: %s", exc)
        return 1
    return 0


if __name__ == '__main__':
    import sys
    from stage_support import call_main
    sys.exit(call_main(run))
