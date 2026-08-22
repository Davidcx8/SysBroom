import os, shutil
from pathlib import Path
from typing import Tuple, List

def safe_delete_file(path) -> Tuple[bool, str]:
    try:
        os.remove(str(path)); return True, ""
    except FileNotFoundError: return True, ""
    except Exception as e: return False, str(e)

def safe_delete_dir(path) -> Tuple[bool, str]:
    try:
        shutil.rmtree(str(path), ignore_errors=True); return True, ""
    except Exception as e: return False, str(e)

def safe_delete_dir_contents(path) -> List[str]:
    errors = []
    try:
        for item in Path(path).iterdir():
            try:
                if item.is_file(follow_symlinks=False):
                    ok, err = safe_delete_file(item)
                    if not ok: errors.append(err)
                elif item.is_dir(follow_symlinks=False):
                    ok, err = safe_delete_dir(item)
                    if not ok: errors.append(err)
            except Exception as e: errors.append(str(e))
    except Exception as e: errors.append(str(e))
    return errors
