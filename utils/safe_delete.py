import os, shutil
from pathlib import Path
from typing import Tuple, List

def safe_delete_file(path) -> Tuple[bool, str]:
    try:
        os.remove(str(path))
        return True, ""
    except FileNotFoundError:
        return True, ""
    except PermissionError:
        return False, "ARCHIVO_EN_USO"
    except Exception as e:
        return False, str(e)

def safe_delete_dir(path) -> Tuple[bool, str]:
    try:
        shutil.rmtree(str(path), ignore_errors=True); return True, ""
    except Exception as e: return False, str(e)

def safe_delete_dir_contents(path) -> List[str]:
    errors = []
    locked_count = 0
    try:
        for item in Path(path).iterdir():
            try:
                if item.is_file(follow_symlinks=False):
                    ok, err = safe_delete_file(item)
                    if not ok:
                        if err == "ARCHIVO_EN_USO":
                            locked_count += 1
                        else:
                            errors.append(err)
                elif item.is_dir(follow_symlinks=False):
                    ok, err = safe_delete_dir(item)
                    if not ok: errors.append(err)
            except Exception as e:
                errors.append(str(e))
    except Exception as e:
        errors.append(str(e))
        
    if locked_count > 0:
        errors.append(f"{locked_count} archivos bloqueados por Windows (en uso)")
    return errors
