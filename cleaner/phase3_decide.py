from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich import box
from utils.sizes import format_size

PRI_COLOR = {"ALTA": "bold red", "MEDIA": "bold yellow", "BAJA": "bold green"}
PRI_ICON  = {"ALTA": "🔴", "MEDIA": "🟡", "BAJA": "🟢"}

# Teclas de filtro rápido
FILTER_KEYS = {
    "D": "docker",
    "W": "wsl",
    "AI": "ai_tools",
    "P": None,   # filtrar solo ALTA prioridad
}

def show_decision_menu(analysis: Dict[str, Any], auto_mode: bool = False) -> List[Dict]:
    console = Console()
    cats = analysis["categories"]

    if auto_mode:
        for c in cats:
            c["enabled"] = c.get("safe", False)
        return cats

    active_filter: str = ""   # "" = sin filtro, "docker", "wsl", etc.
    show_only_high = False

    while True:
        # ── Calcular lista visible ──────────────────────────────────────────
        visible = cats
        if active_filter:
            visible = [c for c in cats if active_filter in c["id"]]
        if show_only_high:
            visible = [c for c in visible if c.get("priority") == "ALTA"]

        # ── Tabla principal ─────────────────────────────────────────────────
        console.print()
        console.print(Rule(
            "[bold cyan]🧹 SysBroom v3.0 — Selección de Limpieza[/]"
            + (f" [dim][Filtro: {active_filter or 'ALTA'}][/]" if active_filter or show_only_high else ""),
            style="cyan"
        ))
        console.print()

        table = Table(
            box=box.ROUNDED, border_style="cyan",
            header_style="bold cyan", min_width=108
        )
        table.add_column("#",          width=4,  justify="right")
        table.add_column("Estado",     width=8,  justify="center")
        table.add_column("Categoría",            min_width=34)
        table.add_column("Tamaño",     width=12, justify="right")
        table.add_column("Prior.",     width=8,  justify="center")
        table.add_column("¿Por qué?",            min_width=30, style="dim")

        for i, cat in enumerate(visible, 1):
            en  = cat.get("enabled", False)
            pri = cat.get("priority", "BAJA")
            sz  = cat.get("size_bytes", 0)
            st  = "[bold green]✅ ON [/]" if en else "[dim]⬜ OFF[/]"
            nm  = f"{cat.get('emoji', '')} {cat['name']}"
            if not cat.get("safe", True):
                nm += " [bold red]⚠[/]"
            sc  = "bold red" if sz > 500*1024**2 else "yellow" if sz > 50*1024**2 else "white"
            why = cat.get("why_delete", cat.get("details", ""))[:55]
            table.add_row(
                str(i), st, nm,
                f"[{sc}]{format_size(sz)}[/]" if sz > 0 else "[dim]—[/]",
                f"[{PRI_COLOR.get(pri, 'white')}]{PRI_ICON.get(pri, '')} {pri}[/]",
                why
            )

        console.print(table)

        # ── Panel de estado ─────────────────────────────────────────────────
        sel_bytes = sum(c.get("size_bytes", 0) for c in cats if c.get("enabled"))
        sel_count = sum(1 for c in cats if c.get("enabled"))
        total_bytes = analysis.get("total_recoverable_bytes", 0)

        console.print(Panel(
            f"  💾 [bold cyan]Seleccionado: {format_size(sel_bytes)}[/]  "
            f"[dim]/ Máximo disponible: {format_size(total_bytes)}[/]  "
            f"  [bold]{sel_count}[/] de [bold]{len(cats)}[/] categorías activas",
            border_style="dim cyan", padding=(0, 1)
        ))

        # ── Ayuda de teclado ────────────────────────────────────────────────
        console.print(
            "\n[bold cyan]→[/] [bold white]#[/]=toggle  "
            "[bold white]A[/]=todo  [bold white]N[/]=nada  "
            "[bold white]D[/]=filtro Docker  [bold white]W[/]=filtro WSL  "
            "[bold white]AI[/]=filtro IA  [bold white]P[/]=solo prioridad ALTA  "
            "[bold white]X[/]=quitar filtro  "
            "[bold white]I#[/]=detalle  "
            "[bold white]ENTER[/]=continuar  [bold white]Q[/]=salir\n"
        )

        try:
            raw = console.input("  Opción: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(0)

        # ── Procesar entrada ────────────────────────────────────────────────
        if raw == "":
            if not any(c.get("enabled") for c in cats):
                console.print("[red]Selecciona al menos una categoría.[/]")
                console.input("  ENTER para continuar...")
                continue
            break

        elif raw == "Q":
            raise SystemExit(0)

        elif raw == "A":
            for c in cats:
                if active_filter:
                    if active_filter in c["id"]:
                        c["enabled"] = c.get("safe", False)
                else:
                    c["enabled"] = c.get("safe", False)

        elif raw == "N":
            for c in cats:
                if active_filter:
                    if active_filter in c["id"]:
                        c["enabled"] = False
                else:
                    c["enabled"] = False

        elif raw == "D":
            active_filter = "docker"
            show_only_high = False

        elif raw == "W":
            active_filter = "wsl"
            show_only_high = False

        elif raw == "AI":
            active_filter = "ai"
            show_only_high = False

        elif raw == "P":
            active_filter = ""
            show_only_high = not show_only_high

        elif raw == "X":
            active_filter = ""
            show_only_high = False

        elif raw.startswith("I") and raw[1:].isdigit():
            # Modo detalle
            idx = int(raw[1:]) - 1
            if 0 <= idx < len(visible):
                _show_category_detail(visible[idx], console)
                console.input("\n  ENTER para volver...")

        elif raw.isdigit() and 1 <= int(raw) <= len(visible):
            idx = int(raw) - 1
            c = visible[idx]
            if not c.get("safe", True) and not c.get("enabled", False):
                console.print(
                    f"\n[bold yellow]⚠ '{c['name']}' requiere confirmación individual por elemento.[/]"
                )
                if console.input("  ¿Activar de todas formas? (s/N): ").strip().lower() == "s":
                    c["enabled"] = True
            else:
                c["enabled"] = not c.get("enabled", False)

    return cats


def _show_category_detail(cat: Dict, console: Console):
    """Muestra desglose detallado de una categoría."""
    console.print()
    console.print(Rule(
        f"[bold white]{cat.get('emoji', '')} {cat['name']}[/]",
        style="cyan"
    ))
    console.print(Panel(
        f"  🗂  [bold]ID:[/]          {cat['id']}\n"
        f"  📊 [bold]Tamaño:[/]     {format_size(cat.get('size_bytes', 0))}\n"
        f"  🎯 [bold]Prioridad:[/]  {PRI_ICON.get(cat.get('priority','BAJA'),'')} {cat.get('priority','BAJA')}\n"
        f"  🛡  [bold]¿Seguro?:[/]  {'Sí' if cat.get('safe') else '⚠ Requiere confirmación'}\n"
        f"  ❓ [bold]Por qué borrar:[/]\n"
        f"     [dim]{cat.get('why_delete', cat.get('details', 'Sin descripción'))}[/]",
        border_style="cyan", padding=(1, 2)
    ))

    # Mostrar meta si existe
    meta = cat.get("meta", {})
    apps = meta.get("apps", {})
    if apps:
        t = Table(title="Desglose de apps", box=box.SIMPLE, header_style="bold dim")
        t.add_column("Aplicación", min_width=20)
        t.add_column("Tamaño", width=14, justify="right")
        for app_name, info in apps.items():
            t.add_row(app_name, format_size(info.get("size_bytes", 0)))
        console.print(t)

    repos = meta.get("repos", [])
    if repos:
        t = Table(title="Repositorios git inactivos", box=box.SIMPLE, header_style="bold dim")
        t.add_column("Repo", min_width=24)
        t.add_column("Último commit", width=14)
        t.add_column("Meses inactivo", width=16, justify="right")
        t.add_column("Tamaño", width=14, justify="right")
        for r in repos[:10]:
            t.add_row(r["name"], r["last_commit"],
                      f"{r['months_inactive']:.0f} meses",
                      format_size(r.get("size_bytes", 0)))
        console.print(t)

    ai_data = meta.get("ai_data", {})
    if ai_data:
        items = ai_data.get("junk", []) + ai_data.get("review", [])
        if items:
            t = Table(title="Herramientas IA detectadas", box=box.SIMPLE, header_style="bold dim")
            t.add_column("Herramienta", width=18)
            t.add_column("Ítem", min_width=28)
            t.add_column("Tamaño", width=12, justify="right")
            t.add_column("Tipo", width=10, justify="center")
            for item in sorted(items, key=lambda x: -x.get("size_bytes", 0))[:12]:
                kind_icon = "🔴" if item["kind"] == "JUNK" else "🟡"
                t.add_row(
                    item["tool"], item["label"][:35],
                    format_size(item.get("size_bytes", 0)),
                    f"{kind_icon} {item['kind']}"
                )
            console.print(t)


def confirm_old_projects(repos, console):
    selected = []
    console.print(Panel(
        "📁 [bold yellow]Proyectos Git Antiguos[/]\n[dim]Confirma uno a uno cuáles eliminar.[/dim]",
        border_style="yellow"
    ))
    for repo in repos:
        nm = repo.get("name", "?")
        sz = format_size(repo.get("size_bytes", 0))
        lc = repo.get("last_commit", "?")[:10]
        mo = repo.get("months_inactive", 0)
        console.print(f"  [cyan]{nm}[/] [dim]({sz} · último commit {lc} · {mo:.0f} meses)[/]")
        console.print(f"  [dim]{repo.get('path', '')}[/]")
        try:
            if console.input("  ¿Eliminar? (s/N): ").strip().lower() == "s":
                selected.append(repo)
                console.print("  [bold red]→ Marcado para eliminar[/]")
            else:
                console.print("  [dim]→ Conservado[/]")
        except Exception:
            break
    return selected
