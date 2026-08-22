import os, subprocess, json, time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.sizes import get_dir_size, get_file_size, get_dir_file_count

USER_TEMP    = Path(os.environ.get("TEMP", "C:/Users/Public/AppData/Local/Temp"))
SYSTEM_TEMP  = Path("C:/Windows/Temp")
PREFETCH_DIR = Path("C:/Windows/Prefetch")
WIN_UPDATE   = Path("C:/Windows/SoftwareDistribution/Download")
THUMB_DIR    = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Explorer"
LOCALAPP     = Path(os.environ.get("LOCALAPPDATA", ""))
APPDATA      = Path(os.environ.get("APPDATA", ""))

DEFAULT_PROJECT_PATHS = [
    Path.home() / "Desktop", Path.home() / "Documents",
    Path.home() / "Downloads", Path.home() / "source",
    Path.home() / "projects", Path.home() / "dev",
]

# ── Por qué borrar — justificaciones para cada categoría ──────────────────────
WHY_DELETE = {
    "windows_temp":   "Archivos temporales del usuario. Windows los genera constantemente y no son necesarios después de su uso.",
    "system_temp":    "Temporales del sistema. Se acumulan tras actualizaciones e instalaciones.",
    "prefetch":       "Datos de precarga de apps. Windows los regenera automáticamente al ejecutar programas.",
    "recycle_bin":    "Archivos en la papelera que ya elegiste eliminar pero siguen ocupando disco.",
    "windows_update": "Paquetes de actualización ya instalados. Windows no los necesita para actualizaciones futuras.",
    "thumbnails":     "Caché de miniaturas de imágenes. Se regenera al abrir carpetas con imágenes.",
    "dump_files":     "Volcados de memoria de errores anteriores. Útiles para diagnóstico, pero seguros de borrar si ya fueron analizados.",
    "app_cache":      "Cachés de navegadores y aplicaciones. Se regeneran al usar las apps.",
    "docker":         "Imágenes, contenedores y volúmenes de Docker sin uso activo.",
    "wsl":            "Archivos temporales y paquetes obsoletos dentro de distribuciones WSL.",
    "dns_cache":      "Tabla DNS local. Limpiarla fuerza resolución fresca y puede mejorar conectividad.",
    "old_projects":   "Repositorios git sin commits en más de 6 meses. Posiblemente abandonados.",
    "ai_tools":       "Cachés, logs y sesiones expiradas de herramientas de IA. Se regeneran automáticamente.",
    "ai_models":      "Modelos de lenguaje locales (Ollama, HuggingFace, LM Studio). Elimina los que ya no uses.",
    "app_residues":   "Carpetas dejadas por programas desinstalados que ya no tienen dueño.",
    "dev_orphans":    "Entornos de desarrollo (venvs, node_modules) en proyectos sin actividad.",
}

def _why(cat_id: str) -> str:
    return WHY_DELETE.get(cat_id, "")

def scan_all(console=None) -> Dict[str, Any]:
    def log(m):
        if console:
            try:
                console.log(f"[dim]{m}[/dim]")
            except Exception:
                pass

    results = {}

    # ── Escaneos paralelos para velocidad ─────────────────────────────────────
    def do_user_temp():
        return "windows_temp", {
            "path": str(USER_TEMP),
            "size_bytes": get_dir_size(USER_TEMP),
            "file_count": get_dir_file_count(USER_TEMP),
            "exists": USER_TEMP.exists(),
            "why_delete": _why("windows_temp"),
        }

    def do_system_temp():
        return "system_temp", {
            "path": str(SYSTEM_TEMP),
            "size_bytes": get_dir_size(SYSTEM_TEMP),
            "file_count": get_dir_file_count(SYSTEM_TEMP),
            "exists": SYSTEM_TEMP.exists(),
            "why_delete": _why("system_temp"),
        }

    def do_prefetch():
        return "prefetch", {
            "path": str(PREFETCH_DIR),
            "size_bytes": get_dir_size(PREFETCH_DIR),
            "file_count": get_dir_file_count(PREFETCH_DIR),
            "exists": PREFETCH_DIR.exists(),
            "why_delete": _why("prefetch"),
        }

    def do_recycle():
        log("Calculando Papelera de Reciclaje...")
        return "recycle_bin", {**_scan_recycle(), "why_delete": _why("recycle_bin")}

    def do_windows_update():
        return "windows_update", {
            "path": str(WIN_UPDATE),
            "size_bytes": get_dir_size(WIN_UPDATE),
            "exists": WIN_UPDATE.exists(),
            "why_delete": _why("windows_update"),
        }

    def do_thumbnails():
        return "thumbnails", {**_scan_thumbnails(), "why_delete": _why("thumbnails")}

    def do_dumps():
        return "dump_files", {**_scan_dumps(), "why_delete": _why("dump_files")}

    def do_app_cache():
        return "app_cache", {**{"caches": _scan_app_caches()}, "why_delete": _why("app_cache")}

    def do_docker():
        log("Consultando Docker...")
        return "docker", {**_scan_docker(), "why_delete": _why("docker")}

    def do_wsl():
        log("Consultando WSL...")
        return "wsl", {**_scan_wsl(), "why_delete": _why("wsl")}

    def do_old_projects():
        log("Buscando proyectos git inactivos...")
        return "old_projects", {**_scan_old_projects(DEFAULT_PROJECT_PATHS), "why_delete": _why("old_projects")}

    tasks = [
        do_user_temp, do_system_temp, do_prefetch,
        do_recycle, do_windows_update, do_thumbnails,
        do_dumps, do_app_cache, do_docker, do_wsl, do_old_projects,
    ]

    log("Iniciando escaneo paralelo de Windows...")
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fn): fn.__name__ for fn in tasks}
        for future in as_completed(futures):
            try:
                key, val = future.result()
                results[key] = val
                log(f"  ✓ {key}")
            except Exception as e:
                log(f"  ⚠ Error en {futures[future]}: {e}")

    results["dns_cache"] = {"size_bytes": 0, "available": True, "why_delete": _why("dns_cache")}
    return results


# ── Funciones de escaneo individuales ─────────────────────────────────────────

def _scan_recycle():
    size = 0
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(New-Object -ComObject Shell.Application).Namespace(0xA).Items()|"
             "ForEach-Object{$_.Size}|Measure-Object -Sum|Select-Object -ExpandProperty Sum"],
            capture_output=True, text=True, timeout=10
        )
        v = r.stdout.strip()
        if v and v.replace(".", "").isdigit():
            size = int(float(v))
    except Exception:
        pass
    return {"size_bytes": size}

def _scan_thumbnails():
    size, files = 0, []
    try:
        if THUMB_DIR.exists():
            for f in THUMB_DIR.glob("thumbcache_*.db"):
                s = get_file_size(f)
                size += s
                files.append({"path": str(f), "size_bytes": s, "name": f.name})
    except Exception:
        pass
    return {"size_bytes": size, "files": files, "path": str(THUMB_DIR)}

def _scan_dumps():
    paths = [
        Path("C:/Windows"),
        Path("C:/Windows/Minidump"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "CrashDumps",
    ]
    files, total = [], 0
    for dp in paths:
        try:
            if dp.exists():
                for f in list(dp.glob("*.dmp")) + list(dp.glob("*.mdmp")):
                    s = get_file_size(f)
                    total += s
                    files.append({"path": str(f), "name": f.name, "size_bytes": s})
        except Exception:
            pass
    return {"files": files, "size_bytes": total, "count": len(files)}

def _scan_app_caches():
    """Caché de aplicaciones (navegadores, comunicación, IDEs)."""
    cache_paths = {
        # Navegadores
        "Chrome":   LOCALAPP / "Google/Chrome/User Data/Default/Cache",
        "Edge":     LOCALAPP / "Microsoft/Edge/User Data/Default/Cache",
        "Firefox":  APPDATA  / "Mozilla/Firefox/Profiles",
        # Dev
        "npm":      LOCALAPP / "npm-cache",
        "pip":      LOCALAPP / "pip/cache",
        "yarn":     LOCALAPP / "Yarn/Cache",
        "VS Code":  LOCALAPP / "Programs/Microsoft VS Code/.cache",
        # Comunicación
        "Discord":  LOCALAPP / "Discord/Cache",
        "Teams":    LOCALAPP / "Microsoft/Teams/Service Worker/CacheStorage",
        "Slack":    APPDATA  / "Slack/Cache",
        "Zoom":     APPDATA  / "Zoom/data/Cache",
        # Productividad
        "Spotify":  LOCALAPP / "Spotify/Data",
        "Notion":   APPDATA  / "Notion/Cache",
    }
    result = {}
    for name, path in cache_paths.items():
        if path.exists():
            # Firefox tiene múltiples perfiles
            if name == "Firefox" and path.is_dir():
                total = 0
                for profile in path.iterdir():
                    cache = profile / "cache2"
                    if cache.exists():
                        total += get_dir_size(cache)
                if total > 0:
                    result[name] = {"path": str(path), "size_bytes": total}
            else:
                sz = get_dir_size(path)
                if sz > 0:
                    result[name] = {"path": str(path), "size_bytes": sz}
    return result

def _scan_docker():
    res = {
        "available": False, "dangling_images": [], "stopped_containers": [],
        "volumes": [], "build_cache_bytes": 0, "total_size_bytes": 0, "error": None,
    }
    try:
        c = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=8)
        if c.returncode != 0:
            res["error"] = "Docker no está corriendo."
            return res
        res["available"] = True

        imgs = subprocess.run(
            ["docker", "images", "--filter", "dangling=true", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=15
        )
        for line in imgs.stdout.strip().splitlines():
            if line.strip():
                try:
                    res["dangling_images"].append(json.loads(line))
                except Exception:
                    pass

        ctrs = subprocess.run(
            ["docker", "ps", "--filter", "status=exited", "--filter", "status=created",
             "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=15
        )
        for line in ctrs.stdout.strip().splitlines():
            if line.strip():
                try:
                    res["stopped_containers"].append(json.loads(line))
                except Exception:
                    pass

        vols = subprocess.run(
            ["docker", "volume", "ls", "--filter", "dangling=true", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=15
        )
        for line in vols.stdout.strip().splitlines():
            if line.strip():
                try:
                    res["volumes"].append(json.loads(line))
                except Exception:
                    pass

        df = subprocess.run(["docker", "system", "df"], capture_output=True, text=True, timeout=20)
        for line in df.stdout.splitlines():
            if "build cache" in line.lower():
                for p in line.split():
                    parsed = _parse_docker_size(p)
                    if parsed > 0:
                        res["build_cache_bytes"] = parsed
                        break

        res["total_size_bytes"] = (
            res["build_cache_bytes"] + len(res["dangling_images"]) * 50 * 1024 * 1024
        )
    except FileNotFoundError:
        res["error"] = "Docker no encontrado en PATH."
    except subprocess.TimeoutExpired:
        res["error"] = "Timeout consultando Docker."
    except Exception as e:
        res["error"] = str(e)
    return res

def _parse_docker_size(s):
    s = s.strip().upper().replace(" ", "")
    for suf, mult in [("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024), ("B", 1)]:
        if s.endswith(suf):
            try:
                return int(float(s[:-len(suf)]) * mult)
            except Exception:
                return 0
    return 0

def _scan_wsl():
    res = {"available": False, "distros": [], "tmp_size_bytes": 0, "error": None}
    try:
        c = subprocess.run(
            ["wsl.exe", "--list", "--quiet"],
            capture_output=True, text=True, timeout=8, encoding="utf-16-le"
        )
        if c.returncode == 0:
            res["available"] = True
            res["distros"] = [d.strip() for d in c.stdout.splitlines() if d.strip()]
            try:
                tmp = subprocess.run(
                    ["wsl.exe", "du", "-sb", "/tmp"],
                    capture_output=True, text=True, timeout=10
                )
                if tmp.returncode == 0:
                    parts = tmp.stdout.strip().split()
                    if parts and parts[0].isdigit():
                        res["tmp_size_bytes"] = int(parts[0])
            except Exception:
                pass
    except FileNotFoundError:
        res["error"] = "WSL no encontrado."
    except Exception as e:
        res["error"] = str(e)
    return res

def _scan_old_projects(paths, months=6):
    cutoff = datetime.now() - timedelta(days=months * 30)
    repos, total = [], 0
    for base in paths:
        if not base.exists():
            continue
        try:
            for item in base.iterdir():
                if not item.is_dir() or not (item / ".git").exists():
                    continue
                try:
                    r = subprocess.run(
                        ["git", "-C", str(item), "log", "-1", "--format=%ci"],
                        capture_output=True, text=True, timeout=8
                    )
                    ls = r.stdout.strip()
                    if ls:
                        lc = datetime.strptime(ls[:19], "%Y-%m-%d %H:%M:%S")
                        if lc < cutoff:
                            sz = get_dir_size(item)
                            total += sz
                            repos.append({
                                "path": str(item), "name": item.name,
                                "last_commit": ls[:10],
                                "months_inactive": round((datetime.now() - lc).days / 30, 1),
                                "size_bytes": sz,
                            })
                except Exception:
                    pass
        except Exception:
            pass
    repos.sort(key=lambda x: x["size_bytes"], reverse=True)
    return {"repos": repos, "count": len(repos), "total_size_bytes": total}
