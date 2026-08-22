import sys, os, json, subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

TASK_NAME   = "SysBroom_Limpieza_Programada"
CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_PROFILE = {
    "windows_temp":   True,
    "system_temp":    True,
    "prefetch":       True,
    "recycle_bin":    True,
    "windows_update": True,
    "app_cache":      True,
    "dns_cache":      True,
    "docker_dangling":True,
    "wsl_clean":      True,
    "kill_zombies":   True,
    # v3.0 — nuevas categorías
    "ai_tools":       True,    # cachés expiradas de IA (seguras)
    "ai_models":      False,   # modelos locales — requieren confirmación
    "app_residues":   False,   # residuos de apps — requieren confirmación
}

PROFILE_LABELS = {
    "windows_temp":   "Temporales de usuario (%TEMP%)",
    "system_temp":    "Temporales de Windows (C:\\Windows\\Temp)",
    "recycle_bin":    "Vaciar Papelera de reciclaje",
    "prefetch":       "Archivos Prefetch",
    "windows_update": "Cache Windows Update",
    "app_cache":      "Cache de Navegadores y Apps",
    "dns_cache":      "Limpiar cache DNS",
    "docker_dangling":"Eliminar imagenes huerfanas Docker",
    "wsl_clean":      "Limpiar /tmp y paquetes en WSL",
    "kill_zombies":   "Terminar procesos Zombie",
    "ai_tools":       "Limpiar caches de herramientas IA (Claude, Cursor, Aider...)",
    "ai_models":      "Modelos IA locales (Ollama, HuggingFace, LM Studio) [interactivo]",
    "app_residues":   "Residuos de apps desinstaladas [interactivo]",
}

import re as _re

def _validate_time(t: str) -> bool:
    return bool(_re.match(r"^\d{1,2}:\d{2}$", t.strip()))


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "schedule": {"day": "Sunday", "time": "10:00"},
        "profile": DEFAULT_PROFILE,
    }


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def interactive_schedule_wizard(console: Console):
    cfg = load_config()
    console.print(Panel(
        "📅 [bold white]Asistente de Programación y Perfil de Limpieza[/]\n"
        "[dim]Configura cuándo y qué se limpiará automáticamente.[/dim]",
        border_style="cyan"
    ))

    dias = [
        ("Monday", "Lunes"), ("Tuesday", "Martes"), ("Wednesday", "Miércoles"),
        ("Thursday", "Jueves"), ("Friday", "Viernes"), ("Saturday", "Sábado"),
        ("Sunday", "Domingo"),
    ]

    console.print("\n[bold cyan]1. Selecciona el día de la semana:[/bold cyan]")
    for i, (_, es) in enumerate(dias, 1):
        console.print(f"  [{i}] {es}")
    console.print("  [8] Todos los días (Diario)")

    day_choice = input("\n  Opción (1-8, Enter=Domingo): ").strip()
    if day_choice == "8":
        schedule_type, day_val, day_str = "Daily", "Daily", "Todos los días"
    else:
        idx = int(day_choice) - 1 if day_choice.isdigit() and 1 <= int(day_choice) <= 7 else 6
        schedule_type, day_val, day_str = "Weekly", dias[idx][0], dias[idx][1]

    console.print("\n[bold cyan]2. Hora de ejecución (formato 24h, ej: 03:00, 14:30):[/bold cyan]")
    while True:
        time_val = input("  Hora (Enter=10:00): ").strip()
        if not time_val:
            time_val = "10:00"
            break
        if _validate_time(time_val):
            break
        console.print("  [red]Formato inválido. Usa HH:MM (ej: 03:30)[/]")

    console.print("\n[bold cyan]3. Perfil de Limpieza:[/bold cyan]")
    prof = cfg.get("profile", DEFAULT_PROFILE)

    for key, label in PROFILE_LABELS.items():
        actual = "✅ SÍ" if prof.get(key, DEFAULT_PROFILE.get(key, False)) else "⬜ NO"
        cambiar = input(f"  ¿Incluir {label}? [{actual}] (Enter=mantener / n=No / s=Sí): ").strip().lower()
        if cambiar == "n":
            prof[key] = False
        elif cambiar == "s":
            prof[key] = True

    cfg["schedule"] = {
        "type": schedule_type, "day": day_val,
        "day_name": day_str, "time": time_val,
    }
    cfg["profile"] = prof
    save_config(cfg)

    python_exe  = sys.executable
    script_path = Path(__file__).parent / "sysbroom.py"
    ps_trigger  = (
        f"-Daily -At '{time_val}'"
        if schedule_type == "Daily"
        else f"-Weekly -DaysOfWeek {day_val} -At '{time_val}'"
    )

    ps_script = f"""
$a = New-ScheduledTaskAction -Execute '{python_exe}' -Argument '"{script_path}" --auto' -WorkingDirectory '{script_path.parent}'
$t = New-ScheduledTaskTrigger {ps_trigger}
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable $true -MultipleInstances IgnoreNew
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $a -Trigger $t -Settings $s -Principal $p -Force | Out-Null
Write-Host "OK"
"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=20
        )
        if "OK" in r.stdout:
            active_count = sum(1 for v in prof.values() if v)
            console.print(Panel(
                f"✅ [bold green]Tarea Programada en Windows con Éxito[/]\n\n"
                f"  📆 Frecuencia:    [bold cyan]{day_str}[/]\n"
                f"  🕙 Hora:          [bold cyan]{time_val}[/]\n"
                f"  🛡️ Categorías:   [bold white]{active_count} de {len(prof)} activas[/]",
                border_style="green"
            ))
        else:
            console.print(f"[red]Error al registrar tarea:[/] {r.stderr.strip()}")
    except Exception as e:
        console.print(f"[red]{e}[/]")


def remove_schedule(console: Console):
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false"],
            capture_output=True, timeout=15
        )
        console.print(f"[green]Tarea '{TASK_NAME}' eliminada de Windows.[/]")
    except Exception as e:
        console.print(f"[red]{e}[/]")


def show_schedule_status(console: Console):
    cfg = load_config()
    sch  = cfg.get("schedule", {})
    prof = cfg.get("profile", {})

    t = Table(
        title="📅 Estado de la Programación y Perfil",
        box=box.ROUNDED, border_style="cyan"
    )
    t.add_column("Propiedad",      width=24)
    t.add_column("Configuración",  width=44)
    t.add_row("Día / Frecuencia", str(sch.get("day_name", sch.get("day", "No configurado"))))
    t.add_row("Hora programada",  str(sch.get("time", "No configurada")))
    active = sum(1 for v in prof.values() if v)
    t.add_row("Categorías activas", f"{active} de {len(prof)} seleccionadas")
    console.print(t)

    # Mostrar qué categorías están activas
    active_labels = [PROFILE_LABELS.get(k, k) for k, v in prof.items() if v]
    if active_labels:
        console.print("\n[dim]Categorías activas en el perfil:[/]")
        for lbl in active_labels:
            console.print(f"  [dim]✅ {lbl}[/]")

    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue | "
             f"Select-Object TaskName, State, @{{N='NextRun';E={{(Get-ScheduledTaskInfo -TaskName $_.TaskName).NextRunTime}}}} | "
             f"Format-List"],
            capture_output=True, text=True, timeout=10
        )
        if r.stdout.strip():
            console.print(f"\n[dim]{r.stdout.strip()}[/dim]")
        else:
            console.print("\n[yellow]La tarea no está registrada en Windows Task Scheduler.[/yellow]")
    except Exception:
        pass