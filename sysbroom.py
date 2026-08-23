"""SysBroom v3.0 — Sistema de Limpieza Inteligente para PC"""
import sys, os, argparse, ctypes
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Forzar UTF-8 en stdout/stderr para soportar emojis en terminales modernos
import io as _io
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from utils.sizes import format_size
from cleaner import phase1_scan, phase2_analyze, phase3_decide, phase4_clean, phase5_report, phase_processes
from cleaner.docker_audit import full_docker_audit, show_docker_report, interactive_docker_cleanup
from cleaner.wsl_audit import full_wsl_audit, show_wsl_report, clean_and_compact_wsl
from cleaner.ai_audit import ai_scan_all, show_ai_report, interactive_ai_cleanup
from cleaner.apps_audit import apps_scan_all, show_apps_report, interactive_apps_cleanup
from scheduler import interactive_schedule_wizard, remove_schedule, show_schedule_status, load_config

VERSION = "3.0.0"
# force_terminal=True evita el renderer legado de Windows que no soporta Unicode
console = Console(force_terminal=True, emoji=True)

# Banner estilo "Gemini CLI" (bloques sólidos)
BANNER_LINES = [
    r"██        ██████  ██    ██  ██████  ████████  ████████   ███████   ███████  ██     ██ ",
    r" ██      ██    ██  ██  ██  ██    ██ ██     ██ ██     ██ ██     ██ ██     ██ ███   ███ ",
    r"  ██     ██         ████   ██       ██     ██ ██     ██ ██     ██ ██     ██ ████ ████ ",
    r"   ██     ██████     ██     ██████  ████████  ████████  ██     ██ ██     ██ ██ ███ ██ ",
    r"  ██           ██    ██          ██ ██     ██ ██   ██   ██     ██ ██     ██ ██     ██ ",
    r" ██      ██    ██    ██    ██    ██ ██     ██ ██    ██  ██     ██ ██     ██ ██     ██ ",
    r"██        ██████     ██     ██████  ████████  ██     ██  ███████   ███████  ██     ██ "
]

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

from rich.text import Text

def banner():
    console.print()
    # Degradado horizontal: Azul oscuro (#0055FF) -> Verde Terminal (#00FF41) predominando el verde
    start_rgb = (0, 85, 255)    # Azul profundo
    end_rgb = (0, 255, 65)      # Verde terminal brillante
    max_len = max(len(l) for l in BANNER_LINES)
    
    for line in BANNER_LINES:
        t = Text()
        for i, char in enumerate(line):
            ratio = i / max_len if max_len > 0 else 0
            # Aceleramos un poco la transición para que predomine el verde
            # Usando una curva simple: ratio = ratio ** 0.7
            curved_ratio = ratio ** 0.7
            
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * curved_ratio)
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * curved_ratio)
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * curved_ratio)
            t.append(char, style=f"rgb({r},{g},{b})")
        console.print(t)
        
    console.print(
        f"\n  [dim]v{VERSION} | {datetime.now().strftime('%d/%m/%Y %H:%M')}[/dim]\n"
    )
    if not is_admin():
        console.print(
            "  [bold yellow]⚠ Sin privilegios de Administrador[/]\n"
            "  [dim]Recomendado: clic derecho → Ejecutar como administrador.[/dim]\n"
        )

def hdr(n, name, desc):
    console.print()
    console.print(Rule(
        f"[bold white]FASE {n}[/] — [bold cyan]{name}[/]  [dim]{desc}[/dim]",
        style="cyan"
    ))
    console.print()


def _tip_controls():
    """Muestra un recordatorio de atajos de teclado para usuarios no experimentados."""
    console.print(Panel(
        "  [bold white]Atajos de teclado:[/]\n"
        "  [bold cyan]Ctrl+C[/] → Detener/cancelar el proceso actual en cualquier momento\n"
        "  [bold cyan]Q + ENTER[/] → Salir del menú de selección\n"
        "  [bold cyan]ENTER[/] → Confirmar selección",
        title="[dim]ℹ Controles[/]",
        border_style="dim", padding=(0, 2)
    ))
    console.print()


def _warn_no_changes():
    """Avisa al usuario que no haga cambios al sistema mientras corre el escaneo."""
    scan_time = datetime.now().strftime("%H:%M:%S")
    console.print(Panel(
        f"  [bold yellow]⚠ No instales, desinstales ni borres archivos[/]\n"
        f"  [dim]mientras SysBroom está en ejecución. Los cambios hechos\n"
        f"  después del escaneo ([bold]{scan_time}[/]) no serán detectados\n"
        f"  y el análisis puede quedar desactualizado.[/dim]",
        border_style="yellow", padding=(0, 2)
    ))
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Modos de ejecución
# ─────────────────────────────────────────────────────────────────────────────

def run_scan_only(dry_run: bool = False):
    """Diagnóstico completo: Windows + Docker + WSL + Procesos + IA + Apps."""
    banner()
    _tip_controls()
    _warn_no_changes()
    hdr(1, "ESCANEO COMPLETO", "Analizando Windows, Docker, WSL, IA, apps y procesos...")

    # ── Escaneo base Windows ──────────────────────────────────────────────────
    scan = phase1_scan.scan_all(console=console)

    # ── Inyectar IA y Apps al scan para análisis unificado ────────────────────
    console.log("[dim]Escaneando herramientas IA...[/dim]")
    scan["ai"] = ai_scan_all(console=None)

    console.log("[dim]Escaneando aplicaciones y residuos...[/dim]")
    scan["apps"] = apps_scan_all(console=None)

    analysis = phase2_analyze.analyze(scan)

    # ── Tabla de categorías detectadas ────────────────────────────────────────
    table = Table(
        title="📂 [bold white]Diagnóstico Completo del Sistema[/]",
        box=box.ROUNDED, border_style="cyan",
        header_style="bold cyan", min_width=108
    )
    table.add_column("",         width=4)
    table.add_column("Categoría",               min_width=34)
    table.add_column("Tamaño",   width=13,       justify="right")
    table.add_column("Prioridad", width=9,       justify="center")
    table.add_column("¿Por qué borrar?",         min_width=30, style="dim")

    pri_colors = {"ALTA": "bold red", "MEDIA": "yellow", "BAJA": "green"}
    pri_icons  = {"ALTA": "🔴", "MEDIA": "🟡", "BAJA": "🟢"}
    for cat in analysis["categories"]:
        sz  = cat.get("size_bytes", 0)
        pri = cat.get("priority", "BAJA")
        sc = "bold red" if sz > 500*1024**2 else "yellow" if sz > 50*1024**2 else "white"
        table.add_row(
            cat.get("emoji", ""),
            cat["name"],
            f"[{sc}]{format_size(sz)}[/]" if sz > 0 else "[dim]—[/]",
            f"[{pri_colors.get(pri, 'white')}]{pri_icons.get(pri, '')} {pri}[/]",
            cat.get("why_delete", cat.get("details", ""))[:55],
        )

    console.print(table)
    console.print(
        f"\n  💾 [bold]Total recuperable estimado:[/] "
        f"[bold cyan]{format_size(analysis['total_recoverable_bytes'])}[/]\n"
        f"  [dim]Ejecuta [bold]sb[/bold] o [bold]sb dry[/bold] para proceder con la limpieza.[/dim]\n"
    )

    # ── Procesos ──────────────────────────────────────────────────────────────
    hdr("1b", "PROCESOS Y PUERTOS", "Escaneando procesos y puertos...")
    pdata = phase_processes.scan_processes_and_ports(console=console)
    phase_processes.show_process_report(pdata, console)


def run_ai_only(dry_run: bool = False):
    """Auditoría dedicada de herramientas y ecosistema de IA."""
    banner()
    hdr("🤖", "AUDITORÍA DE IA", "Cachés, modelos, sesiones y herramientas de IA...")
    data = ai_scan_all(console=console)
    show_ai_report(data, console)
    if data.get("junk") or data.get("review"):
        interactive_ai_cleanup(data, console, dry_run=dry_run)


def run_apps_only(dry_run: bool = False):
    """Auditoría dedicada de aplicaciones, extensiones y entornos de desarrollo."""
    banner()
    hdr("📦", "AUDITORÍA DE APPS", "Residuos, extensiones, venvs y cachés de desarrollo...")
    data = apps_scan_all(console=console)
    show_apps_report(data, console)
    if data.get("grand_total_bytes", 0) > 0:
        interactive_apps_cleanup(data, console, dry_run=dry_run)


def run_docker_only(dry_run: bool = False):
    banner()
    hdr("🐳", "DOCKER AUDITORÍA", "Imágenes, Contenedores, Volúmenes y Redes...")
    data = full_docker_audit(console=console)
    show_docker_report(data, console)
    if data.get("available"):
        interactive_docker_cleanup(data, console)


def run_wsl_only(dry_run: bool = False):
    banner()
    hdr("🐧", "WSL AUDITORÍA Y COMPACTACIÓN", "Discos VHDX, paquetes y temporales...")
    data = full_wsl_audit(console=console)
    show_wsl_report(data, console)
    if data.get("available"):
        clean_and_compact_wsl(data, console)


def run_pipeline(auto: bool = False, dry_run: bool = False):
    """Pipeline completo: Windows + IA + Apps + Docker + WSL."""
    banner()
    if not auto:
        _tip_controls()
        _warn_no_changes()
    hdr(1, "ESCANEO", "Detectando elementos limpiables en todo el sistema...")

    # Scan Windows base
    scan = phase1_scan.scan_all(console=console)
    pdata = phase_processes.scan_processes_and_ports(console=console)

    # Integrar datos IA y Apps al scan para análisis unificado
    console.log("[dim]Escaneando herramientas IA...[/dim]")
    ai_data = ai_scan_all(console=None)  # silencioso en pipeline
    scan["ai"] = ai_data

    console.log("[dim]Escaneando aplicaciones y residuos...[/dim]")
    apps_data = apps_scan_all(console=None)  # silencioso en pipeline
    scan["apps"] = apps_data

    analysis = phase2_analyze.analyze(scan)

    if auto:
        cfg = load_config()
        prof = cfg.get("profile", {})
        for c in analysis["categories"]:
            cid = c["id"]
            if cid in prof:
                c["enabled"] = prof[cid]
            else:
                c["enabled"] = c.get("safe", False)
        cats = analysis["categories"]
        if prof.get("kill_zombies", True):
            for z in pdata.get("zombie", []):
                phase_processes.kill_process(z["pid"], force=True)
    else:
        hdr(2, "DECISIÓN", "Selección de categorías a limpiar...")
        try:
            cats = phase3_decide.show_decision_menu(analysis, auto_mode=False)
        except SystemExit:
            return

    phase_num = 3 if not auto else 2
    hdr(phase_num, "LIMPIEZA", f"{'Simulando' if dry_run else 'Ejecutando'} limpieza segura...")
    cleanup = phase4_clean.run_cleanup(cats, scan, console, dry_run=dry_run)

    hdr(phase_num + 1, "REPORTE", "Generando reporte...")
    phase5_report.generate_report(cleanup, analysis, console)


def run_dry_run():
    """Simula el pipeline completo sin borrar nada."""
    console.print(Panel(
        "📋 [bold yellow]Modo Simulación (Dry-Run)[/]\n"
        "[dim]Se mostrará todo lo que se limpiaría sin borrar nada.[/]",
        border_style="yellow"
    ))
    run_pipeline(auto=False, dry_run=True)


def show_last_report():
    """Abre el último reporte en la terminal."""
    logs = sorted(Path(_ROOT / "logs").glob("sysbroom_*.md"), reverse=True)
    if not logs:
        console.print("[yellow]No hay reportes previos.[/]")
        return
    last = logs[0]
    console.print(Rule(f"[bold white]Último reporte: {last.name}[/]", style="green"))
    try:
        console.print(last.read_text(encoding="utf-8"))
    except Exception as e:
        console.print(f"[red]No se pudo leer el reporte: {e}[/]")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="sysbroom",
        description=f"SysBroom v{VERSION} — Sistema de Limpieza Inteligente"
    )
    p.add_argument("--auto",       action="store_true",  help="Limpieza automática según perfil")
    p.add_argument("--scan-only",  action="store_true",  help="Solo diagnóstico, sin limpiar")
    p.add_argument("--processes",  action="store_true",  help="Procesos y puertos")
    p.add_argument("--docker",     action="store_true",  help="Auditoría Docker granular")
    p.add_argument("--wsl",        action="store_true",  help="Auditoría WSL granular")
    p.add_argument("--ai",         action="store_true",  help="Auditoría de herramientas IA")
    p.add_argument("--apps",       action="store_true",  help="Auditoría de apps y residuos")
    p.add_argument("--dry-run",    action="store_true",  help="Simular sin borrar nada")
    p.add_argument("--schedule",   action="store_true",  help="Asistente de programación")
    p.add_argument("--unschedule", action="store_true",  help="Eliminar tarea programada")
    p.add_argument("--status",     action="store_true",  help="Estado de la programación")
    p.add_argument("--history",    action="store_true",  help="Historial de limpiezas")
    p.add_argument("--report",     action="store_true",  help="Ver último reporte")
    p.add_argument("--version",    action="version",     version=f"SysBroom v{VERSION}")
    a = p.parse_args()

    dry = a.dry_run

    try:
        if a.schedule:
            interactive_schedule_wizard(console)
        elif a.unschedule:
            remove_schedule(console)
        elif a.status:
            show_schedule_status(console)
        elif a.history:
            phase5_report.show_history(console)
        elif a.report:
            show_last_report()
        elif a.docker:
            run_docker_only(dry_run=dry)
        elif a.wsl:
            run_wsl_only(dry_run=dry)
        elif a.ai:
            run_ai_only(dry_run=dry)
        elif a.apps:
            run_apps_only(dry_run=dry)
        elif a.processes:
            banner()
            pdata = phase_processes.scan_processes_and_ports(console=console)
            phase_processes.show_process_report(pdata, console)
        elif a.scan_only:
            run_scan_only(dry_run=dry)
        elif a.dry_run:
            run_dry_run()
        elif a.auto:
            run_pipeline(auto=True, dry_run=dry)
        else:
            run_pipeline(auto=False, dry_run=dry)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrumpido.[/]")
        sys.exit(0)


if __name__ == "__main__":
    main()