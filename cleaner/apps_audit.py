"""
cleaner/apps_audit.py  —  SysBroom v3.0
Auditoría de programas instalados, extensiones de navegador,
entornos de desarrollo y residuos de desinstalaciones.
Limpieza sin dejar rastros/entradas huérfanas.
"""
import os, re, subprocess, winreg
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

HOME     = Path.home()
LOCALAPP = Path(os.environ.get("LOCALAPPDATA", ""))
APPDATA  = Path(os.environ.get("APPDATA", ""))
PROGDATA = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData"))
NOW      = datetime.now(timezone.utc)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except Exception:
            return 0
    total = 0
    try:
        for e in os.scandir(path):
            try:
                if e.is_file(follow_symlinks=False):
                    total += e.stat(follow_symlinks=False).st_size
                elif e.is_dir(follow_symlinks=False):
                    total += _size(Path(e.path))
            except Exception:
                pass
    except Exception:
        pass
    return total

def _age_days(path: Path) -> Optional[float]:
    if not path.exists():
        return None
    try:
        if path.is_file():
            mtime = path.stat().st_mtime
        else:
            newest = None
            for root, _, files in os.walk(path):
                if root.replace(str(path), "").count(os.sep) > 3:
                    continue
                for f in files:
                    try:
                        mtime = Path(root, f).stat().st_mtime
                        if newest is None or mtime > newest:
                            newest = mtime
                    except Exception:
                        pass
            mtime = newest if newest else path.stat().st_mtime
        return (NOW - datetime.fromtimestamp(mtime, tz=timezone.utc)).days
    except Exception:
        return None

def _fmt_age(days: Optional[float]) -> str:
    if days is None:
        return "?"
    if days == 0:
        return "hoy"
    if days < 7:
        return f"{int(days)}d"
    if days < 30:
        return f"{int(days//7)} sem."
    if days < 365:
        return f"{int(days//30)} mes(es)"
    return f"{int(days//365)} año(s)"

def _fmt_size(b: int) -> str:
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0:
            return f"{b:.1f} {u}"
        b /= 1024.0
    return f"{b:.1f} PB"

# ──────────────────────────────────────────────────────────────────────────────
# Registro de Windows — programas instalados
# ──────────────────────────────────────────────────────────────────────────────

UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

def _read_installed_programs() -> List[Dict]:
    programs = []
    seen = set()
    for hive, key_path in UNINSTALL_KEYS:
        try:
            hkey = winreg.OpenKey(hive, key_path)
            count = winreg.QueryInfoKey(hkey)[0]
            for i in range(count):
                try:
                    sub_name = winreg.EnumKey(hkey, i)
                    sub_key = winreg.OpenKey(hkey, sub_name)
                    def rv(name, default=""):
                        try:
                            return winreg.QueryValueEx(sub_key, name)[0]
                        except Exception:
                            return default

                    display_name = rv("DisplayName")
                    if not display_name or display_name in seen:
                        continue
                    seen.add(display_name)

                    install_loc = rv("InstallLocation")
                    publisher = rv("Publisher")
                    version = rv("DisplayVersion")
                    uninstall_str = rv("UninstallString")
                    install_date_raw = rv("InstallDate")  # YYYYMMDD
                    size_kb = rv("EstimatedSize", 0)
                    try:
                        size_kb = int(size_kb)
                    except Exception:
                        size_kb = 0

                    install_date = None
                    if install_date_raw and len(str(install_date_raw)) == 8:
                        try:
                            install_date = datetime.strptime(str(install_date_raw), "%Y%m%d")
                        except Exception:
                            pass

                    programs.append({
                        "name": display_name,
                        "publisher": publisher,
                        "version": version,
                        "install_location": install_loc,
                        "size_kb": size_kb,
                        "install_date": install_date,
                        "has_uninstaller": bool(uninstall_str),
                    })
                except Exception:
                    pass
            winreg.CloseKey(hkey)
        except Exception:
            pass
    return programs

def _scan_program_residues() -> List[Dict]:
    """
    Detecta carpetas en %APPDATA%/%LOCALAPPDATA% que corresponden
    a programas ya NO instalados (sin entrada en el registro).
    """
    programs = _read_installed_programs()
    installed_names_lower = {p["name"].lower() for p in programs}
    # También extraer palabras clave de publishers/nombres
    known_keywords = set()
    for p in programs:
        for word in re.split(r'[\s\-\_\.]', p["name"].lower()):
            if len(word) > 4:
                known_keywords.add(word)

    residues = []
    search_dirs = [APPDATA, LOCALAPP, PROGDATA]

    for base in search_dirs:
        if not base.exists():
            continue
        try:
            for folder in base.iterdir():
                if not folder.is_dir():
                    continue
                fname = folder.name.lower()
                # Excluir carpetas del sistema
                if fname in {"microsoft", "windows", "temp", "cache", "google",
                             "mozilla", "packages", "programs", "roaming",
                             "local", "locallow", "nvidia", "intel"}:
                    continue
                # Verificar si hay algún programa instalado que "matchee"
                matched = any(
                    fname in name.lower() or name.lower() in fname
                    for name in installed_names_lower
                )
                if not matched:
                    sz = _size(folder)
                    age = _age_days(folder)
                    # Solo reportar si tiene tamaño significativo y es vieja
                    if sz > 1024 * 1024 and age is not None and age > 30:
                        residues.append({
                            "name": folder.name,
                            "path": str(folder),
                            "size_bytes": sz,
                            "age_days": age,
                            "age_str": _fmt_age(age),
                            "base_dir": str(base),
                        })
        except Exception:
            pass

    residues.sort(key=lambda x: -x["size_bytes"])
    return residues

# ──────────────────────────────────────────────────────────────────────────────
# Extensiones de navegador
# ──────────────────────────────────────────────────────────────────────────────

EXTENSION_NAMES_CACHE: Dict[str, str] = {}

def _get_extension_name(ext_dir: Path) -> str:
    """Lee el manifest.json de una extensión para obtener su nombre."""
    manifest = ext_dir / "manifest.json"
    if not manifest.exists():
        # Puede estar en una sub-versión
        for sub in ext_dir.iterdir() if ext_dir.is_dir() else []:
            if sub.is_dir():
                manifest = sub / "manifest.json"
                break
    if manifest.exists():
        try:
            data = json_safe_load(manifest)
            name = data.get("name", "")
            if name.startswith("__MSG_"):
                # Internacionalizado, buscar en _locales
                locale_msg = (manifest.parent / "_locales" / "en" / "messages.json")
                if locale_msg.exists():
                    msgs = json_safe_load(locale_msg)
                    key = name.replace("__MSG_", "").replace("__", "").lower()
                    for k, v in msgs.items():
                        if k.lower() == key:
                            return v.get("message", name)
            return name
        except Exception:
            pass
    return ext_dir.parent.name if ext_dir.parent else ext_dir.name

def json_safe_load(path: Path) -> dict:
    try:
        return __import__("json").loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}

def _scan_browser_extensions() -> Dict[str, Any]:
    """Escanea extensiones de Chrome y Edge."""
    browsers = {
        "Chrome": LOCALAPP / "Google" / "Chrome" / "User Data",
        "Edge":   LOCALAPP / "Microsoft" / "Edge" / "User Data",
        "Brave":  LOCALAPP / "BraveSoftware" / "Brave-Browser" / "User Data",
    }
    result = []

    for browser_name, user_data in browsers.items():
        if not user_data.exists():
            continue
        # Buscar perfiles (Default, Profile 1, etc.)
        profiles = [user_data / "Default"] + list(user_data.glob("Profile*"))
        for profile in profiles:
            ext_dir = profile / "Extensions"
            if not ext_dir.exists():
                continue
            prefs_file = profile / "Preferences"
            enabled_exts: set = set()
            disabled_exts: set = set()
            try:
                prefs = json_safe_load(prefs_file)
                ext_settings = prefs.get("extensions", {}).get("settings", {})
                for ext_id, ext_data in ext_settings.items():
                    if ext_data.get("state") == 1:
                        enabled_exts.add(ext_id)
                    else:
                        disabled_exts.add(ext_id)
            except Exception:
                pass

            for ext_folder in ext_dir.iterdir() if ext_dir.is_dir() else []:
                if not ext_folder.is_dir():
                    continue
                ext_id = ext_folder.name
                sz = _size(ext_folder)
                age = _age_days(ext_folder)
                name = _get_extension_name(ext_folder)
                is_enabled = ext_id in enabled_exts
                is_disabled = ext_id in disabled_exts

                result.append({
                    "browser": browser_name,
                    "profile": profile.name,
                    "id": ext_id,
                    "name": name or ext_id,
                    "size_bytes": sz,
                    "age_days": age,
                    "age_str": _fmt_age(age),
                    "enabled": is_enabled,
                    "disabled": is_disabled,
                    # Sugerencia: eliminar si desactivada y vieja
                    "suggest_remove": is_disabled and (age is not None and age > 30),
                })

    disabled = [e for e in result if e.get("suggest_remove")]
    return {
        "all": result,
        "disabled_old": disabled,
        "total_size": sum(e["size_bytes"] for e in result),
        "disabled_size": sum(e["size_bytes"] for e in disabled),
    }

# ──────────────────────────────────────────────────────────────────────────────
# Entornos de desarrollo huérfanos
# ──────────────────────────────────────────────────────────────────────────────

def _scan_orphan_venvs() -> List[Dict]:
    """Detecta entornos virtuales Python en proyectos sin actividad."""
    venvs = []
    search_roots = [
        HOME / "Desktop", HOME / "Documents", HOME / "source",
        HOME / "projects", HOME / "dev", HOME / "Downloads",
    ]
    venv_markers = {"pyvenv.cfg", "Scripts/python.exe", "bin/python"}

    for base in search_roots:
        if not base.exists():
            continue
        try:
            for root, dirs, _ in os.walk(str(base)):
                # No profundizar más de 4 niveles
                depth = root.replace(str(base), "").count(os.sep)
                if depth > 4:
                    dirs.clear()
                    continue
                for d in list(dirs):
                    candidate = Path(root) / d
                    # Es un venv si tiene pyvenv.cfg o Scripts/python.exe
                    is_venv = (candidate / "pyvenv.cfg").exists() or \
                              (candidate / "Scripts" / "python.exe").exists()
                    if is_venv:
                        sz = _size(candidate)
                        age = _age_days(candidate)
                        # Considerar huérfano si > 3 meses inactivo
                        if age is not None and age > 90 and sz > 20 * 1024 * 1024:
                            venvs.append({
                                "path": str(candidate),
                                "parent": str(candidate.parent),
                                "name": candidate.name,
                                "size_bytes": sz,
                                "age_days": age,
                                "age_str": _fmt_age(age),
                                "reason": f"Entorno virtual sin actividad en {_fmt_age(age)}"
                            })
                        dirs.remove(d)  # No entrar dentro del venv
        except Exception:
            pass

    venvs.sort(key=lambda x: -x["size_bytes"])
    return venvs

def _scan_orphan_node_modules() -> List[Dict]:
    """Detecta node_modules en proyectos sin actividad reciente."""
    results = []
    search_roots = [
        HOME / "Desktop", HOME / "Documents", HOME / "source",
        HOME / "projects", HOME / "dev",
    ]

    for base in search_roots:
        if not base.exists():
            continue
        try:
            for root, dirs, _ in os.walk(str(base)):
                depth = root.replace(str(base), "").count(os.sep)
                if depth > 4:
                    dirs.clear()
                    continue
                if "node_modules" in dirs:
                    nm_path = Path(root) / "node_modules"
                    project_dir = Path(root)
                    # Edad del proyecto (sin contar node_modules)
                    pkg_json = project_dir / "package.json"
                    age = _age_days(pkg_json) if pkg_json.exists() else _age_days(project_dir)
                    sz = _size(nm_path)
                    if age is not None and age > 60 and sz > 50 * 1024 * 1024:
                        results.append({
                            "path": str(nm_path),
                            "project": str(project_dir),
                            "project_name": project_dir.name,
                            "size_bytes": sz,
                            "age_days": age,
                            "age_str": _fmt_age(age),
                            "reason": f"node_modules de proyecto inactivo ({_fmt_age(age)})"
                        })
                    dirs.remove("node_modules")
        except Exception:
            pass

    results.sort(key=lambda x: -x["size_bytes"])
    return results

def _scan_dev_caches() -> List[Dict]:
    """Cachés globales de herramientas de desarrollo."""
    items = []
    caches = [
        (LOCALAPP / "npm-cache",          "npm cache global",             "JUNK"),
        (LOCALAPP / "Yarn" / "Cache",     "Yarn cache global",            "JUNK"),
        (HOME / ".cargo" / "registry",    "Cargo (Rust) registry cache",  "JUNK"),
        (HOME / ".gradle" / "caches",     "Gradle build cache",           "JUNK"),
        (HOME / ".m2" / "repository",     "Maven repository local",       "REVIEW"),
        (HOME / ".nuget" / "packages",    "NuGet packages cache",         "REVIEW"),
        (LOCALAPP / "pip" / "cache",      "pip cache global",             "JUNK"),
        (HOME / ".cache" / "pip",         "pip cache (linux-style)",      "JUNK"),
        (HOME / ".pnpm-store",            "pnpm global store",            "REVIEW"),
    ]
    for path, label, kind in caches:
        if path.exists():
            sz = _size(path)
            age = _age_days(path)
            if sz > 0:
                items.append({
                    "path": str(path),
                    "label": label,
                    "kind": kind,
                    "size_bytes": sz,
                    "age_days": age,
                    "age_str": _fmt_age(age),
                    "why_delete": f"Caché de paquetes de {label.split()[0]}. Se regenera al compilar/instalar."
                })
    return items

# ──────────────────────────────────────────────────────────────────────────────
# Función principal
# ──────────────────────────────────────────────────────────────────────────────

def apps_scan_all(console=None) -> Dict[str, Any]:
    def log(msg: str):
        if console:
            try:
                console.log(f"[dim]{msg}[/dim]")
            except Exception:
                pass

    log("Apps: Leyendo registro de Windows...")
    installed = _read_installed_programs()

    log("Apps: Buscando residuos de programas desinstalados...")
    residues = _scan_program_residues()

    log("Apps: Escaneando extensiones de navegador...")
    ext_data = _scan_browser_extensions()

    log("Apps: Buscando entornos virtuales Python huérfanos...")
    orphan_venvs = _scan_orphan_venvs()

    log("Apps: Buscando node_modules huérfanos...")
    orphan_nm = _scan_orphan_node_modules()

    log("Apps: Escaneando cachés de herramientas de desarrollo...")
    dev_caches = _scan_dev_caches()

    total_residues_bytes = sum(r["size_bytes"] for r in residues)
    total_ext_bytes = ext_data.get("disabled_size", 0)
    total_venv_bytes = sum(v["size_bytes"] for v in orphan_venvs)
    total_nm_bytes = sum(n["size_bytes"] for n in orphan_nm)
    total_cache_bytes = sum(c["size_bytes"] for c in dev_caches if c["kind"] == "JUNK")

    return {
        "available": True,
        "installed_count": len(installed),
        "residues": residues,
        "extensions": ext_data,
        "orphan_venvs": orphan_venvs,
        "orphan_node_modules": orphan_nm,
        "dev_caches": dev_caches,
        "total_residues_bytes": total_residues_bytes,
        "total_extensions_bytes": total_ext_bytes,
        "total_venv_bytes": total_venv_bytes,
        "total_nm_bytes": total_nm_bytes,
        "total_cache_bytes": total_cache_bytes,
        "grand_total_bytes": (
            total_residues_bytes + total_ext_bytes +
            total_venv_bytes + total_nm_bytes + total_cache_bytes
        ),
    }


def show_apps_report(data: Dict[str, Any], console) -> None:
    from rich.table import Table
    from rich.panel import Panel
    from rich.rule import Rule
    from rich import box
    from utils.sizes import format_size

    residues = data.get("residues", [])
    ext_data = data.get("extensions", {})
    venvs    = data.get("orphan_venvs", [])
    nm       = data.get("orphan_node_modules", [])
    caches   = data.get("dev_caches", [])

    console.print(Panel(
        f"  📦 Programas instalados:         [bold white]{data.get('installed_count', 0)}[/]\n"
        f"  🗑  Residuos de desinstalaciones: [bold white]{len(residues)}[/] "
        f"· [bold red]{format_size(data.get('total_residues_bytes', 0))}[/]\n"
        f"  🧩 Extensiones desactivadas:     [bold white]{len(ext_data.get('disabled_old', []))}[/] "
        f"· [bold yellow]{format_size(data.get('total_extensions_bytes', 0))}[/]\n"
        f"  🐍 Venvs Python huérfanos:       [bold white]{len(venvs)}[/] "
        f"· [bold yellow]{format_size(data.get('total_venv_bytes', 0))}[/]\n"
        f"  📦 node_modules huérfanos:       [bold white]{len(nm)}[/] "
        f"· [bold yellow]{format_size(data.get('total_nm_bytes', 0))}[/]\n"
        f"  🔧 Cachés de herramientas dev:   [bold white]{len(caches)}[/] "
        f"· [bold cyan]{format_size(data.get('total_cache_bytes', 0))}[/]",
        title="📦 [bold white]Apps — Auditoría de Software y Residuos[/]",
        border_style="blue", padding=(1, 3)
    ))

    # Residuos de programas
    if residues:
        console.print(Rule("[bold red]🗑 RESIDUOS DE PROGRAMAS DESINSTALADOS[/]", style="red"))
        t = Table(box=box.ROUNDED, border_style="red", header_style="bold red", min_width=90)
        t.add_column("Carpeta", min_width=26)
        t.add_column("Ruta base", width=20, style="dim")
        t.add_column("Tamaño", width=12, justify="right")
        t.add_column("Inactivo", width=12, justify="center")
        for r in residues[:20]:
            sz = r["size_bytes"]
            sc = "red" if sz > 200*1024**2 else "yellow" if sz > 50*1024**2 else "white"
            t.add_row(r["name"], Path(r["base_dir"]).name,
                      f"[{sc}]{format_size(sz)}[/]", r["age_str"])
        console.print(t)

    # Extensiones desactivadas
    disabled = ext_data.get("disabled_old", [])
    if disabled:
        console.print(Rule("[bold yellow]🧩 EXTENSIONES DE NAVEGADOR DESACTIVADAS[/]", style="yellow"))
        t2 = Table(box=box.ROUNDED, border_style="yellow", header_style="bold yellow", min_width=90)
        t2.add_column("Navegador", width=10)
        t2.add_column("Extensión", min_width=30)
        t2.add_column("ID", width=24, style="dim")
        t2.add_column("Tamaño", width=12, justify="right")
        t2.add_column("Inactiva", width=12, justify="center")
        for e in disabled[:15]:
            t2.add_row(e["browser"], e["name"][:38], e["id"][:22],
                       format_size(e["size_bytes"]), e["age_str"])
        console.print(t2)

    # Venvs huérfanos
    if venvs:
        console.print(Rule("[bold yellow]🐍 ENTORNOS VIRTUALES PYTHON HUÉRFANOS[/]", style="yellow"))
        t3 = Table(box=box.ROUNDED, border_style="yellow", header_style="bold yellow", min_width=90)
        t3.add_column("Nombre", width=20)
        t3.add_column("Proyecto", min_width=30, style="dim")
        t3.add_column("Tamaño", width=12, justify="right")
        t3.add_column("Inactivo", width=12, justify="center")
        for v in venvs[:10]:
            t3.add_row(v["name"], str(Path(v["parent"]).name),
                       format_size(v["size_bytes"]), v["age_str"])
        console.print(t3)

    # node_modules
    if nm:
        console.print(Rule("[bold yellow]📦 NODE_MODULES HUÉRFANOS[/]", style="yellow"))
        t4 = Table(box=box.ROUNDED, border_style="yellow", header_style="bold yellow", min_width=90)
        t4.add_column("Proyecto", min_width=26)
        t4.add_column("Ruta", min_width=30, style="dim")
        t4.add_column("Tamaño", width=12, justify="right")
        t4.add_column("Inactivo", width=12, justify="center")
        for n in nm[:10]:
            t4.add_row(n["project_name"], str(Path(n["project"]))[:-len(n["project_name"])-1][:30],
                       format_size(n["size_bytes"]), n["age_str"])
        console.print(t4)

    # Cachés de herramientas
    if caches:
        console.print(Rule("[bold cyan]🔧 CACHÉS DE HERRAMIENTAS DE DESARROLLO[/]", style="cyan"))
        t5 = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan", min_width=90)
        t5.add_column("Herramienta", min_width=28)
        t5.add_column("Tipo", width=10, justify="center")
        t5.add_column("Tamaño", width=12, justify="right")
        t5.add_column("Inactivo", width=12, justify="center")
        for c in caches:
            kind_icon = "🔴 JUNK" if c["kind"] == "JUNK" else "🟡 REVISAR"
            t5.add_row(c["label"], kind_icon, format_size(c["size_bytes"]), c["age_str"])
        console.print(t5)


def interactive_apps_cleanup(data: Dict[str, Any], console, dry_run: bool = False) -> Dict:
    from utils.sizes import format_size
    from utils.safe_delete import safe_delete_dir, safe_delete_dir_contents
    from rich.panel import Panel
    import shutil

    report = {"deleted": [], "skipped": [], "errors": [], "freed_bytes": 0}

    # ── CACHÉS DE DESARROLLO (JUNK) ──
    junk_caches = [c for c in data.get("dev_caches", []) if c["kind"] == "JUNK"]
    if junk_caches:
        total = sum(c["size_bytes"] for c in junk_caches)
        console.print(Panel(
            f"🔧 [bold]{len(junk_caches)} cachés de herramientas de desarrollo[/] — [bold cyan]{format_size(total)}[/]\n"
            f"[dim]npm, pip, Yarn, Cargo, Gradle, etc. Se regeneran automáticamente.[/]",
            border_style="cyan"
        ))
        ans = input("  ¿Limpiar todas las cachés de desarrollo? (s/N): ").strip().lower()
        if ans == "s":
            for c in junk_caches:
                p = Path(c["path"])
                try:
                    if not dry_run:
                        safe_delete_dir_contents(p)
                        report["freed_bytes"] += c["size_bytes"]
                        report["deleted"].append(c["path"])
                        console.print(f"  ✅ {c['label']} — [green]{format_size(c['size_bytes'])}[/]")
                    else:
                        console.print(f"  [dim][DRY-RUN] {c['label']}[/]")
                        report["skipped"].append(c["path"])
                except Exception as e:
                    report["errors"].append(str(e))

    # ── VENVS HUÉRFANOS ──
    venvs = data.get("orphan_venvs", [])
    if venvs:
        console.print(f"\n🐍 [bold yellow]{len(venvs)} entornos virtuales huérfanos encontrados:[/]")
        for v in venvs:
            console.print(f"  · {v['name']} ({v['age_str']}) — [bold]{format_size(v['size_bytes'])}[/]")
            console.print(f"    [dim]{v['path']}[/]")
            ans = input("    ¿Eliminar? (s/N): ").strip().lower()
            if ans == "s":
                try:
                    if not dry_run:
                        safe_delete_dir(Path(v["path"]))
                        report["freed_bytes"] += v["size_bytes"]
                        report["deleted"].append(v["path"])
                        console.print("    ✅ Eliminado")
                    else:
                        console.print("    [dim][DRY-RUN] Omitido[/]")
                        report["skipped"].append(v["path"])
                except Exception as e:
                    report["errors"].append(str(e))
            else:
                report["skipped"].append(v["path"])

    # ── NODE_MODULES ──
    nms = data.get("orphan_node_modules", [])
    if nms:
        console.print(f"\n📦 [bold yellow]{len(nms)} node_modules huérfanos encontrados:[/]")
        for n in nms:
            console.print(f"  · {n['project_name']} ({n['age_str']}) — [bold]{format_size(n['size_bytes'])}[/]")
            ans = input("    ¿Eliminar node_modules? (s/N): ").strip().lower()
            if ans == "s":
                try:
                    if not dry_run:
                        safe_delete_dir(Path(n["path"]))
                        report["freed_bytes"] += n["size_bytes"]
                        report["deleted"].append(n["path"])
                        console.print("    ✅ Eliminado")
                    else:
                        console.print("    [dim][DRY-RUN] Omitido[/]")
                        report["skipped"].append(n["path"])
                except Exception as e:
                    report["errors"].append(str(e))

    # ── RESIDUOS DE PROGRAMAS ──
    residues = data.get("residues", [])
    if residues:
        console.print(f"\n🗑 [bold red]{len(residues)} residuos de programas desinstalados:[/]")
        for r in residues[:10]:
            console.print(f"  · {r['name']} ({r['age_str']}) — [bold]{format_size(r['size_bytes'])}[/]")
            console.print(f"    [dim]{r['path']}[/]")
            ans = input("    ¿Eliminar? (s/N): ").strip().lower()
            if ans == "s":
                try:
                    if not dry_run:
                        safe_delete_dir(Path(r["path"]))
                        report["freed_bytes"] += r["size_bytes"]
                        report["deleted"].append(r["path"])
                        console.print("    ✅ Eliminado")
                    else:
                        console.print("    [dim][DRY-RUN] Omitido[/]")
                        report["skipped"].append(r["path"])
                except Exception as e:
                    report["errors"].append(str(e))

    return report
