import os, shutil, stat
from pathlib import Path
from typing import Tuple, List

def safe_delete_file(path) -> Tuple[bool, str]:
    """Elimina un archivo de forma segura, lidiando con permisos."""
    try:
        os.remove(str(path))
        return True, ""
    except FileNotFoundError:
        return True, ""
    except PermissionError:
        try:
            # Archivo de solo lectura o protegido temporalmente
            os.chmod(str(path), stat.S_IWRITE)
            os.remove(str(path))
            return True, ""
        except PermissionError:
            return False, "ARCHIVO_EN_USO"
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)

def safe_delete_dir(path) -> Tuple[bool, str]:
    """Elimina un directorio completo, ignorando errores en archivos bloqueados."""
    def on_error(func, p, exc_info):
        try:
            # Si es un archivo de solo lectura, intentar quitar la restricción
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            # Si definitivamente está bloqueado por otro proceso, se ignora
            # para que shutil.rmtree pueda continuar borrando el resto.
            pass
            
    try:
        shutil.rmtree(str(path), onerror=on_error)
        return True, ""
    except Exception as e:
        return False, str(e)

def safe_delete_dir_contents(path) -> List[str]:
    """Vacia el contenido de un directorio (archivos y subcarpetas)."""
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
                    if not ok: 
                        errors.append(err)
            except Exception as e:
                pass # Ignorar archivos inaccesibles individuales
    except Exception as e:
        errors.append(f"No se pudo acceder a la carpeta: {e}")
        
    if locked_count > 0:
        errors.append(f"{locked_count} archivos de sistema en uso (omitidos de forma segura)")
    return errors
