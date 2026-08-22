import os
from pathlib import Path

def format_size(b: int) -> str:
    if b <= 0: return "0 B"
    for u in ["B","KB","MB","GB","TB"]:
        if b < 1024.0: return f"{b:.1f} {u}"
        b /= 1024.0
    return f"{b:.1f} PB"

def get_dir_size(path) -> int:
    total = 0
    try:
        for e in os.scandir(path):
            try:
                if e.is_file(follow_symlinks=False): total += e.stat(follow_symlinks=False).st_size
                elif e.is_dir(follow_symlinks=False): total += get_dir_size(e.path)
            except: pass
    except: pass
    return total

def get_dir_file_count(path) -> int:
    c = 0
    try:
        for e in os.scandir(path):
            try:
                if e.is_file(follow_symlinks=False): c += 1
                elif e.is_dir(follow_symlinks=False): c += get_dir_file_count(e.path)
            except: pass
    except: pass
    return c

def get_file_size(path) -> int:
    try: return os.path.getsize(path)
    except: return 0
