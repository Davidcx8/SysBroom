import subprocess, os, re
from pathlib import Path
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from utils.sizes import format_size, get_file_size
from cleaner.docker_audit import parse_docker_size

def _run_wsl(distro: str, cmd: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(["wsl.exe", "-d", distro, "-e", "bash", "-c", cmd],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception: return ""

def full_wsl_audit(console: Console = None) -> Dict[str, Any]:
    result = {"available": False, "error": None, "distros": [], "total_vhdx_bytes": 0, "total_reclaimable": 0}
    try:
        c = subprocess.run(["wsl.exe", "--list", "--verbose"],
                           capture_output=True, text=True, timeout=8, encoding="utf-16-le")
        if c.returncode != 0:
            result["error"] = "WSL no está instalado o no hay distribuciones."
            return result
    except FileNotFoundError:
        result["error"] = "WSL no encontrado en el sistema."
        return result
    except Exception as e:
        result["error"] = str(e); return result

    result["available"] = True
    distro_list = []
    for line in c.stdout.strip().splitlines()[1:]:
        line = line.strip()
        if not line: continue
        default = "*" in line
        clean = line.replace("*", "").strip().split()
        if len(clean) >= 3:
            distro_list.append({"name": clean[0], "state": clean[1], "version": clean[2], "default": default})

    localapp = Path(os.environ.get("LOCALAPPDATA", ""))
    vhdx_candidates = list(localapp.glob("Packages/*/LocalState/ext4.vhdx")) + \
                      list(localapp.glob("wsl/*/ext4.vhdx")) + \
                      list(localapp.glob("Docker/wsl/data/ext4.vhdx"))

    for d in distro_list:
        dname = d["name"]
        vhdx_path = None; vhdx_size = 0
        for p in vhdx_candidates:
            if dname.lower() in str(p).lower() or (dname.startswith("Ubuntu") and "CanonicalGroup" in str(p)):
                vhdx_path = str(p); vhdx_size = get_file_size(p); break

        internal_used = 0; apt_cache_size = 0; journal_size = 0; tmp_size = 0

        df_out = _run_wsl(dname, "df -B1 / | tail -1")
        if df_out:
            parts = df_out.split()
            if len(parts) >= 3 and parts[2].isdigit(): internal_used = int(parts[2])

        apt_out = _run_wsl(dname, "du -sb /var/cache/apt/archives 2>/dev/null | cut -f1")
        if apt_out.isdigit(): apt_cache_size = int(apt_out)

        tmp_out = _run_wsl(dname, "du -sb /tmp 2>/dev/null | cut -f1")
        if tmp_out.isdigit(): tmp_size = int(tmp_out)

        j_out = _run_wsl(dname, "journalctl --disk-usage 2>/dev/null")
        if j_out:
            m = re.search(r'([\d\.]+\s*[KMGT]?B)', j_out)
            if m: journal_size = parse_docker_size(m.group(1))

        reclaimable_vhdx = max(0, vhdx_size - internal_used) if vhdx_size > 0 and internal_used > 0 else 0

        dinfo = {
            "name": dname, "state": d["state"], "version": d["version"], "default": d["default"],
            "vhdx_size": vhdx_size, "internal_used": internal_used,
            "reclaimable_vhdx": reclaimable_vhdx, "apt_cache": apt_cache_size,
            "tmp_size": tmp_size, "journal_size": journal_size,
            "cleanable_internal": apt_cache_size + tmp_size + journal_size
        }
        result["distros"].append(dinfo)
        result["total_vhdx_bytes"] += vhdx_size
        result["total_reclaimable"] += (reclaimable_vhdx + dinfo["cleanable_internal"])

    return result

def show_wsl_report(data: Dict[str, Any], console: Console):
    if not data.get("available"):
        console.print(Panel(f"🐧 [bold red]WSL no disponible[/]\n[dim]{data.get('error','')}[/dim]", border_style="red"))
        return

    distros = data.get("distros", [])
    console.print(Panel(
        f"  🐧 Distribuciones instaladas:  [bold white]{len(distros)}[/]\n"
        f"  💾 Espacio físico en disco:    [bold cyan]{format_size(data['total_vhdx_bytes'])}[/]\n"
        f"  🎯 Espacio recuperable total:  [bold green]{format_size(data['total_reclaimable'])}[/] (Basura interna + VHDX a compactar)",
        title="🐧 [bold white]WSL — Auditoría de Disco y Estado[/]", border_style="green", padding=(1, 3)))

    t = Table(box=box.ROUNDED, border_style="green", header_style="bold green", min_width=96)
    t.add_column("Distro", width=22)
    t.add_column("Estado", width=12, justify="center")
    t.add_column("VHDX (Host)", width=13, justify="right")
    t.add_column("Uso Real Linux", width=14, justify="right")
    t.add_column("Caché Apt/Tmp", width=14, justify="right")
    t.add_column("Compactable", width=14, justify="right")

    for d in distros:
        st_color = "green" if d["state"].lower() == "running" else "dim"
        t.add_row(
            f"{'⭐ ' if d['default'] else ''}{d['name']} (v{d['version']})",
            f"[{st_color}]{d['state']}[/]",
            format_size(d["vhdx_size"]) if d["vhdx_size"] > 0 else "[dim]N/A[/]",
            format_size(d["internal_used"]) if d["internal_used"] > 0 else "[dim]—[/]",
            format_size(d["cleanable_internal"]),
            f"[bold green]{format_size(d['reclaimable_vhdx'])}[/]" if d["reclaimable_vhdx"] > 500*1024**2 else format_size(d["reclaimable_vhdx"])
        )
    console.print(t)

def clean_and_compact_wsl(data: Dict[str, Any], console: Console):
    distros = [d for d in data.get("distros", []) if d["state"].lower() == "running" or d["cleanable_internal"] > 0]
    if not distros: return

    console.print("\n[bold cyan]1. Limpiando cachés internas (apt, /tmp, journals)...[/bold cyan]")
    for d in distros:
        dname = d["name"]
        _run_wsl(dname, "sudo apt-get clean && sudo apt-get autoremove -y 2>/dev/null || true")
        _run_wsl(dname, "sudo journalctl --vacuum-time=2d 2>/dev/null || true")
        _run_wsl(dname, "sudo rm -rf /tmp/* 2>/dev/null || true")
        console.print(f"  ✅ Archivos temporales y paquetes liberados en [bold]{dname}[/].")

    console.print("\n[bold cyan]2. Compactación de Discos Virtuales VHDX:[/bold cyan]")
    try: ans = input("  ¿Deseas apagar WSL y compactar las distros ahora? (s/N): ").strip().lower()
    except: return

    if ans == "s":
        console.print("  🛑 Apagando WSL (`wsl --shutdown`)...")
        subprocess.run(["wsl.exe", "--shutdown"], capture_output=True)
        for d in data.get("distros", []):
            if d["reclaimable_vhdx"] > 100*1024**2:
                console.print(f"  ⚡ Compactando [bold]{d['name']}[/]...")
                r = subprocess.run(["wsl.exe", "--manage", d["name"], "--compact"], capture_output=True, text=True)
                if r.returncode == 0: console.print(f"     ✅ [green]{d['name']} compactado con éxito.[/green]")
