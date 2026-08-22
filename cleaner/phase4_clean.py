import os, subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from utils.sizes import format_size, get_dir_size
from utils.safe_delete import safe_delete_dir_contents, safe_delete_file, safe_delete_dir

DRY_RUN = False  # Puede activarse globalmente desde sysbroom.py

def run_cleanup(categories, scan_results, console, dry_run: bool = False) -> Dict[str, Any]:
    global DRY_RUN
    DRY_RUN = dry_run

    report = {
        "started_at": datetime.now().isoformat(),
        "tasks": [], "total_freed_bytes": 0, "total_errors": 0,
        "dry_run": dry_run,
    }
    selected = [c for c in categories if c.get("enabled")]
    if not selected:
        return report

    mode_label = "[bold yellow][DRY-RUN][/]" if dry_run else "[bold green]Limpieza real[/]"
    console.print(Panel(
        f"🚀 {mode_label} — [bold white]{len(selected)} categorías seleccionadas[/]",
        border_style="yellow" if dry_run else "green"
    ))
    if dry_run:
        console.print("[dim]  Modo simulación activo — ningún archivo será eliminado.[/]\n")

    fns = {
        "windows_temp":   lambda: _clean_dir(Path(os.environ.get("TEMP", "C:/Users/Public/AppData/Local/Temp"))),
        "system_temp":    lambda: _clean_dir(Path("C:/Windows/Temp")),
        "prefetch":       lambda: _clean_dir(Path("C:/Windows/Prefetch")),
        "recycle_bin":    _clean_recycle,
        "windows_update": lambda: _clean_dir(Path("C:/Windows/SoftwareDistribution/Download")),
        "thumbnails":     lambda: _clean_thumbs(scan_results),
        "dump_files":     lambda: _clean_dumps(scan_results),
        "app_cache":      lambda: _clean_app_cache(scan_results),
        "docker":         _clean_docker,
        "wsl":            _clean_wsl,
        "dns_cache":      _clean_dns,
        "ai_tools":       lambda: _clean_ai(scan_results),
        "ai_models":      lambda: _clean_ai(scan_results, models_only=True),
        "app_residues":   lambda: _clean_app_residues(scan_results),
        "dev_orphans":    lambda: _clean_dev_orphans(scan_results),
    }

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"),
        BarColumn(30), TaskProgressColumn(),
        console=console, transient=False
    ) as prog:
        ov = prog.add_task("[cyan]Limpieza total...", total=len(selected))
        for cat in selected:
            t = prog.add_task(f"{cat.get('emoji', '')} {cat['name']}...", total=1)
            freed, errs = 0, []
            fn = fns.get(cat["id"])
            if fn:
                try:
                    freed, errs = fn()
                except Exception as e:
                    errs = [str(e)]

            report["total_freed_bytes"] += freed
            report["total_errors"] += len(errs)
            status = "dry_run" if dry_run else ("ok" if not errs else "partial")
            report["tasks"].append({
                "name": cat["name"], "emoji": cat.get("emoji", ""),
                "freed_bytes": freed, "status": status, "errors": errs,
                "why_delete": cat.get("why_delete", ""),
            })
            prog.update(t, completed=1)
            prog.update(ov, advance=1)

            if dry_run:
                console.print(f"  [dim]📋 {cat.get('emoji', '')} {cat['name']} → {format_size(cat.get('size_bytes', 0))} (simulado)[/]")
            elif status == "ok":
                console.print(f"  ✅ {cat.get('emoji', '')} {cat['name']} — [green]{format_size(freed)}[/]")
            else:
                console.print(f"  ⚠️  {cat.get('emoji', '')} {cat['name']} — [yellow]{format_size(freed)}[/] ({len(errs)} errores)")

    report["finished_at"] = datetime.now().isoformat()
    return report


def _should_skip() -> bool:
    return DRY_RUN


def _clean_dir(p):
    if _should_skip():
        return get_dir_size(p) if p.exists() else 0, []
    b = get_dir_size(p) if p.exists() else 0
    errs = safe_delete_dir_contents(p)
    a = get_dir_size(p) if p.exists() else 0
    return max(0, b - a), errs


def _clean_recycle():
    if _should_skip():
        return 0, []
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
            capture_output=True, timeout=20
        )
    except Exception as e:
        return 0, [str(e)]
    return 0, []


def _clean_thumbs(scan):
    if _should_skip():
        return scan.get("thumbnails", {}).get("size_bytes", 0), []
    files = scan.get("thumbnails", {}).get("files", [])
    freed, errs = 0, []
    for f in files:
        p = Path(f["path"])
        sz = f.get("size_bytes", 0)
        ok, err = safe_delete_file(p)
        if ok:
            freed += sz
        elif err:
            errs.append(err)
    return freed, errs


def _clean_dumps(scan):
    if _should_skip():
        return scan.get("dump_files", {}).get("size_bytes", 0), []
    files = scan.get("dump_files", {}).get("files", [])
    freed, errs = 0, []
    for f in files:
        p = Path(f["path"])
        sz = f.get("size_bytes", 0)
        ok, err = safe_delete_file(p)
        if ok:
            freed += sz
        elif err:
            errs.append(err)
    return freed, errs


def _clean_app_cache(scan):
    if _should_skip():
        ac_raw = scan.get("app_cache", {})
        ac = ac_raw.get("caches", ac_raw)
        return sum(v["size_bytes"] for v in ac.values() if isinstance(v, dict)), []
    ac_raw = scan.get("app_cache", {})
    ac = ac_raw.get("caches", ac_raw)
    freed, errs = 0, []
    if isinstance(ac, dict):
        for name, info in ac.items():
            if not isinstance(info, dict):
                continue
            p = Path(info["path"])
            if p.exists():
                b = get_dir_size(p)
                e = safe_delete_dir_contents(p)
                a = get_dir_size(p)
                freed += max(0, b - a)
                errs.extend(e)
    return freed, errs


def _clean_docker():
    if _should_skip():
        return 0, []
    try:
        r = subprocess.run(
            ["docker", "system", "prune", "-f", "--volumes"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if "Total reclaimed space:" in line:
                    raw = line.split(":")[-1].strip()
                    return _parse_sz(raw), []
        return 0, [r.stderr.strip()[:200]] if r.stderr else []
    except FileNotFoundError:
        return 0, ["Docker no encontrado."]
    except Exception as e:
        return 0, [str(e)]


def _clean_wsl():
    if _should_skip():
        return 0, []
    try:
        subprocess.run(["wsl.exe", "rm", "-rf", "/tmp/*"],
                       capture_output=True, text=True, timeout=30)
        return 0, []
    except Exception as e:
        return 0, [str(e)]


def _clean_dns():
    if _should_skip():
        return 0, []
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
        return 0, []
    except Exception as e:
        return 0, [str(e)]


def _clean_ai(scan, models_only: bool = False):
    """Limpia ítems JUNK de la auditoría IA (no los REVIEW que requieren interacción)."""
    ai_data = scan.get("ai", {})
    if not ai_data:
        return 0, []
    if _should_skip():
        junk_bytes = ai_data.get("junk_bytes", 0)
        return (0 if models_only else junk_bytes), []

    freed, errs = 0, []
    items_to_clean = []
    if models_only:
        # Solo modelos de tipo REVIEW de herramientas de modelos — no borrar automáticamente
        return 0, ["Los modelos IA requieren confirmación interactiva. Usa 'sb ai' para gestionarlos."]
    else:
        items_to_clean = ai_data.get("junk", [])

    for item in items_to_clean:
        p = Path(item["path"])
        sz = item.get("size_bytes", 0)
        try:
            if p.is_file():
                ok, err = safe_delete_file(p)
                if ok:
                    freed += sz
                elif err:
                    errs.append(err)
            elif p.is_dir():
                e = safe_delete_dir_contents(p)
                freed += sz
                errs.extend(e)
        except Exception as e:
            errs.append(str(e))
    return freed, errs


def _clean_app_residues(scan):
    """Limpia cachés de herramientas de desarrollo (JUNK). Residuos requieren interacción."""
    apps_data = scan.get("apps", {})
    if not apps_data:
        return 0, []
    if _should_skip():
        return apps_data.get("total_cache_bytes", 0), []

    freed, errs = 0, []
    junk_caches = [c for c in apps_data.get("dev_caches", []) if c["kind"] == "JUNK"]
    for c in junk_caches:
        p = Path(c["path"])
        if p.exists():
            b = get_dir_size(p)
            e = safe_delete_dir_contents(p)
            a = get_dir_size(p)
            freed += max(0, b - a)
            errs.extend(e)
    return freed, errs


def _clean_dev_orphans(scan):
    """Limpia entornos dev huérfanos — requiere interacción."""
    return 0, ["Venvs y node_modules huérfanos requieren confirmación individual. Usa 'sb apps'."]


def _parse_sz(s):
    s = s.strip().upper().replace(" ", "")
    for sf, m in [("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024), ("B", 1)]:
        if s.endswith(sf):
            try:
                return int(float(s[:-len(sf)]) * m)
            except Exception:
                return 0
    return 0
