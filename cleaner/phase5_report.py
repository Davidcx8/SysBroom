import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich import box
from utils.sizes import format_size

LOGS_DIR = Path(__file__).parent.parent / "logs"


def generate_report(report: Dict, analysis: Dict, console: Console) -> str:
    LOGS_DIR.mkdir(exist_ok=True)
    tasks  = report.get("tasks", [])
    total  = report.get("total_freed_bytes", 0)
    dry_run = report.get("dry_run", False)

    try:
        dur = (
            datetime.fromisoformat(report["finished_at"]) -
            datetime.fromisoformat(report["started_at"])
        ).total_seconds()
        dur_str = f"{dur:.1f}s"
    except Exception:
        dur_str = "—"

    # ── Tabla de resultados ──────────────────────────────────────────────────
    table = Table(
        title="📊 [bold white]Resumen Final de Limpieza[/]",
        box=box.ROUNDED, border_style="green" if not dry_run else "yellow",
        header_style="bold green" if not dry_run else "bold yellow"
    )
    table.add_column("",          width=4)
    table.add_column("Categoría", min_width=34)
    table.add_column("Liberado",  width=14, justify="right")
    table.add_column("Estado",    width=14, justify="center")
    table.add_column("Errores",   width=8,  justify="right")

    for t in tasks:
        em   = t.get("emoji", "")
        nm   = t["name"]
        st   = t.get("status", "ok")
        errs = len(t.get("errors", []))
        st_icon = {
            "ok":      "[bold green]✅ OK[/]",
            "partial": "[yellow]⚠ Parcial[/]",
            "error":   "[red]❌ Error[/]",
            "dry_run": "[dim]📋 Simulado[/]",
        }.get(st, "[dim]Omitido[/]")
        table.add_row(
            em, nm, format_size(t.get("freed_bytes", 0)),
            st_icon, f"[red]{errs}[/]" if errs else "[dim]0[/]"
        )

    console.print()
    console.print(table)

    # ── Panel de resumen ─────────────────────────────────────────────────────
    title_mode = "[bold yellow]SysBroom — Simulación[/]" if dry_run else "[bold white]SysBroom — Resultado[/]"
    freed_str  = f"[dim]{format_size(total)} (simulado)[/]" if dry_run else f"[bold cyan]{format_size(total)}[/]"
    console.print(Panel(
        f"{'📋' if dry_run else '🎉'} {'[bold yellow]Simulación completada[/]' if dry_run else '[bold green]¡Limpieza completada![/]'}\n\n"
        f"  💾 [bold]Espacio {'que se liberaría' if dry_run else 'liberado'}:[/]  {freed_str}\n"
        f"  ⏱  [bold]Duración:[/]          {dur_str}\n"
        f"  ⚠️  [bold]Advertencias:[/]      {report.get('total_errors', 0)}\n"
        f"  🗂  [bold]Categorías:[/]        {len(tasks)}",
        title=title_mode,
        border_style="bold yellow" if dry_run else "bold green",
        padding=(1, 4)
    ))

    # ── Sección de justificaciones ────────────────────────────────────────────
    why_items = [(t["name"], t.get("why_delete", "")) for t in tasks if t.get("why_delete")]
    if why_items:
        console.print(Rule("[dim]📋 Por qué se limpió cada categoría[/]", style="dim"))
        for name, why in why_items:
            console.print(f"  [dim]· [bold]{name}:[/bold] {why}[/]")
        console.print()

    # ── Guardar reporte ───────────────────────────────────────────────────────
    now   = datetime.now()
    prefix = "dryrun" if dry_run else "sysbroom"
    fname = LOGS_DIR / f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}.md"
    json_fname = LOGS_DIR / f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}.json"

    # Markdown
    lines = [
        f"# SysBroom — {'[DRY-RUN] ' if dry_run else ''}Reporte {now.strftime('%d/%m/%Y %H:%M:%S')}",
        f"**Espacio {'que se liberaría' if dry_run else 'liberado'}:** {format_size(total)}  ",
        f"**Duración:** {dur_str}",
        f"**Modo:** {'Simulación (dry-run)' if dry_run else 'Limpieza real'}",
        "",
        "## Resumen por categoría",
        "",
        "| # | Categoría | Liberado | Estado | Por qué |",
        "|---|-----------|----------|--------|---------|",
    ]
    for i, t in enumerate(tasks, 1):
        why = t.get("why_delete", "—")[:80]
        lines.append(
            f"| {i} | {t['name']} | {format_size(t.get('freed_bytes', 0))} "
            f"| {t.get('status', 'ok')} | {why} |"
        )

    fname.write_text("\n".join(lines), encoding="utf-8")

    # JSON (para procesamiento futuro)
    try:
        json_data = {
            "timestamp": now.isoformat(),
            "dry_run": dry_run,
            "total_freed_bytes": total,
            "duration_seconds": float(dur_str.replace("s", "")) if dur_str != "—" else 0,
            "tasks": tasks,
        }
        json_fname.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    console.print(f"📄 Reporte guardado: [cyan]{fname.name}[/]  [dim]({fname})[/]\n")
    return str(fname)


def show_history(console: Console, n: int = 10):
    LOGS_DIR.mkdir(exist_ok=True)
    all_reports = sorted(LOGS_DIR.glob("sysbroom_*.md"), reverse=True)[:n]
    all_dry     = sorted(LOGS_DIR.glob("dryrun_*.md"), reverse=True)[:3]

    if not all_reports and not all_dry:
        console.print("[yellow]Sin reportes previos.[/]")
        return

    if all_reports:
        table = Table(
            title="📋 [bold white]Historial de Limpiezas[/]",
            box=box.ROUNDED, border_style="green", header_style="bold green"
        )
        table.add_column("Fecha",   width=22)
        table.add_column("Archivo", min_width=36)
        table.add_column("Detalle", min_width=20, style="dim")

        for r in all_reports:
            ds = r.stem.replace("sysbroom_", "").replace("_", " ")
            try:
                d = datetime.strptime(ds, "%Y%m%d %H%M%S").strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                d = ds
            # Leer primera línea relevante del reporte para el detalle
            detail = ""
            try:
                for line in r.read_text(encoding="utf-8").splitlines():
                    if line.startswith("**Espacio"):
                        detail = line.replace("**Espacio liberado:**", "").strip()
                        break
            except Exception:
                pass
            table.add_row(d, r.name, detail)
        console.print(table)

    if all_dry:
        console.print(f"\n  [dim]Simulaciones recientes: {', '.join(r.name for r in all_dry)}[/]")
