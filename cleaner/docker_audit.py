import subprocess, json, re
from datetime import datetime, timezone
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich import box
from utils.sizes import format_size

def _age_str(iso_str: str) -> str:
    if not iso_str: return "?"
    try:
        iso_str = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days = (now - dt).days
        if days == 0: return "hoy"
        elif days == 1: return "ayer"
        elif days < 7: return f"{days} días"
        elif days < 30: return f"{days // 7} sem."
        elif days < 365: return f"{days // 30} mes(es)"
        else: return f"{days // 365} año(s)"
    except Exception: return "?"

def _fmt_date(iso_str: str) -> str:
    try:
        iso_str = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(iso_str).strftime("%d/%m/%Y %H:%M")
    except Exception: return iso_str[:16] if iso_str else "?"

def _run(cmd: List[str], timeout: int = 20) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception: return ""

def _run_json(cmd: List[str]) -> List[Dict]:
    out = _run(cmd)
    res = []
    for line in out.splitlines():
        if line.strip():
            try: res.append(json.loads(line.strip()))
            except: pass
    return res

def parse_docker_size(s: str) -> int:
    if not s: return 0
    s = s.strip().upper().replace(" ", "").replace(",", ".")
    for suf, mult in [("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024), ("B", 1)]:
        if s.endswith(suf):
            try: return int(float(s[:-len(suf)]) * mult)
            except: return 0
    try: return int(s)
    except: return 0

def full_docker_audit(console: Console = None) -> Dict[str, Any]:
    result = {"available": False, "error": None, "images": [], "containers": [], "volumes": [], "networks": [], "system_df": {}, "reclaimable_bytes": 0, "total_used_bytes": 0}
    check = _run(["docker", "info"])
    if not check:
        result["error"] = "Docker Desktop no está corriendo o no está instalado."
        return result
    result["available"] = True

    imgs_raw = _run_json(["docker", "images", "--no-trunc", "--format", "{{json .}}"])
    ctrs_for_images = _run_json(["docker", "ps", "-a", "--format", "{{json .}}"])

    for img in imgs_raw:
        raw_id = img.get("ID", "")
        short_id = raw_id.replace("sha256:", "")[:12]
        name = img.get("Repository", "<none>")
        tag = img.get("Tag", "<none>")
        size_s = img.get("Size", "0B")
        created = img.get("CreatedAt", img.get("CreatedSince", ""))
        size_b = parse_docker_size(size_s)

        in_use = any(short_id in (c.get("Image", "")[:12]) or f"{name}:{tag}" == c.get("Image", "") for c in ctrs_for_images)
        is_dangling = (name == "<none>" and tag == "<none>")

        result["images"].append({
            "id": short_id, "name": name, "tag": tag,
            "full_name": f"{name}:{tag}" if name != "<none>" else "<none>",
            "size_bytes": size_b, "size_str": size_s,
            "created": _fmt_date(created), "age": _age_str(created),
            "in_use": in_use, "dangling": is_dangling, "safe_to_delete": not in_use
        })

    result["images"].sort(key=lambda x: (-x["size_bytes"], x["name"]))

    ctrs_raw = _run_json(["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"])
    size_map = {}
    for line in _run(["docker", "ps", "-a", "--format", "{{.ID}} {{.Size}}"]).splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2: size_map[parts[0][:12]] = parts[1]

    for ctr in ctrs_raw:
        cid = (ctr.get("ID") or "")[:12]
        status = ctr.get("Status", "")
        result["containers"].append({
            "id": cid, "name": ctr.get("Names", "?"), "image": ctr.get("Image", "?"),
            "status": status, "is_running": status.lower().startswith("up"),
            "created": _fmt_date(ctr.get("CreatedAt", "")), "age": _age_str(ctr.get("CreatedAt", "")),
            "ports": ctr.get("Ports", "—")[:40] if ctr.get("Ports") else "—",
            "size_str": size_map.get(cid, "?"), "safe_to_delete": not status.lower().startswith("up")
        })

    vols_raw = _run_json(["docker", "volume", "ls", "--format", "{{json .}}"])
    used_vols = set()
    for pid in _run(["docker", "ps", "-a", "-q"]).splitlines()[:20]:
        insp = _run(["docker", "inspect", "--format", "{{range .Mounts}}{{.Name}} {{end}}", pid.strip()])
        for v in insp.split(): used_vols.add(v.strip())

    for vol in vols_raw:
        vname = vol.get("Name", "?")
        dangling = vname not in used_vols
        result["volumes"].append({
            "name": vname, "driver": vol.get("Driver", "local"),
            "in_use": not dangling, "dangling": dangling, "safe_to_delete": dangling
        })

    nets_raw = _run_json(["docker", "network", "ls", "--format", "{{json .}}"])
    for net in nets_raw:
        nname = net.get("Name", "")
        if nname in {"bridge", "host", "none"}: continue
        insp = _run(["docker", "network", "inspect", "--format", "{{len .Containers}}", nname])
        cnt = int(insp) if insp.isdigit() else 0
        result["networks"].append({"name": nname, "driver": net.get("Driver", ""), "container_count": cnt, "safe_to_delete": cnt == 0})

    df_out = _run(["docker", "system", "df"])
    result["system_df"]["raw"] = df_out
    for line in df_out.splitlines():
        if "(" in line and "B)" in line.upper():
            m = re.search(r'\((\d+(?:\.\d+)?[KMGT]?B)\)', line, re.IGNORECASE)
            if m: result["reclaimable_bytes"] += parse_docker_size(m.group(1))

    result["total_used_bytes"] = sum(i["size_bytes"] for i in result["images"])
    return result

def show_docker_report(data: Dict[str, Any], console: Console):
    if not data.get("available"):
        console.print(Panel(f"🐳 [bold red]Docker no disponible[/]\n[dim]{data.get('error', '')}[/dim]", border_style="red"))
        return

    imgs, ctrs, vols, nets = data["images"], data["containers"], data["volumes"], data["networks"]
    unused_imgs = [i for i in imgs if not i["in_use"]]
    running_ctrs = [c for c in ctrs if c["is_running"]]
    dangling_vols = [v for v in vols if v["dangling"]]
    unused_nets = [n for n in nets if n["safe_to_delete"]]
    space_unused = sum(i["size_bytes"] for i in unused_imgs)

    console.print(Panel(
        f"  📦 Imágenes totales:          [bold white]{len(imgs)}[/]  ([bold yellow]{len(unused_imgs)} sin uso[/] · [bold red]{sum(1 for i in imgs if i['dangling'])} huérfanas[/])\n"
        f"  📋 Contenedores:              [bold white]{len(ctrs)}[/]  ([bold green]{len(running_ctrs)} corriendo[/] · [bold red]{len(ctrs)-len(running_ctrs)} detenidos[/])\n"
        f"  💾 Volúmenes:                 [bold white]{len(vols)}[/]  ([bold red]{len(dangling_vols)} huérfanos[/])\n"
        f"  🔗 Redes personalizadas:      [bold white]{len(nets)}[/]  ([bold red]{len(unused_nets)} sin uso[/])\n\n"
        f"  💡 Espacio recuperable en imágenes: [bold cyan]{format_size(space_unused)}[/]",
        title="🐳 [bold white]Docker — Auditoría Completa[/]", border_style="blue", padding=(1, 3)))

    console.print(Rule("[bold blue]📦 IMÁGENES[/]", style="blue"))
    t = Table(box=box.ROUNDED, border_style="blue", header_style="bold blue", min_width=96)
    t.add_column("ID", width=13)
    t.add_column("Nombre:Tag", min_width=34)
    t.add_column("Tamaño", width=10, justify="right")
    t.add_column("Creada", width=16)
    t.add_column("Edad", width=10)
    t.add_column("Estado", width=14, justify="center")
    t.add_column("¿Eliminar?", width=12, justify="center")

    for img in imgs:
        estado = "[bold green]✅ EN USO[/]" if img["in_use"] else ("[bold red]🗑 HUÉRFANA[/]" if img["dangling"] else "[yellow]⚠ Sin usar[/]")
        elim = "[dim]No[/]" if img["in_use"] else "[bold green]✅ Sí[/]"
        t.add_row(f"[dim]{img['id']}[/]", img['full_name'], img['size_str'], f"[dim]{img['created']}[/]", img["age"], estado, elim)
    console.print(t)

    console.print(Rule("[bold cyan]📋 CONTENEDORES[/]", style="cyan"))
    t2 = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan", min_width=96)
    t2.add_column("ID", width=13)
    t2.add_column("Nombre", width=24)
    t2.add_column("Imagen", width=26)
    t2.add_column("Estado", width=22)
    t2.add_column("Edad", width=10)
    for c in ctrs:
        st_style = "[bold green]" if c["is_running"] else "[bold red]"
        t2.add_row(f"[dim]{c['id']}[/]", c["name"], f"[dim]{c['image'][:24]}[/]", f"{st_style}{c['status'][:20]}[/]", c["age"])
    console.print(t2)

def interactive_docker_cleanup(data: Dict[str, Any], console: Console):
    imgs = [i for i in data["images"] if i["safe_to_delete"]]
    ctrs = [c for c in data["containers"] if c["safe_to_delete"]]
    vols = [v for v in data["volumes"] if v["safe_to_delete"]]
    if not (imgs or ctrs or vols):
        console.print("[green]✅ Docker ya está limpio. Nada que eliminar.[/]")
        return

    console.print("\n[bold cyan]Opciones de limpieza:[/bold cyan]")
    if imgs: console.print(f"  [1] Eliminar {len(imgs)} imágenes sin usar ({format_size(sum(i['size_bytes'] for i in imgs))})")
    if ctrs: console.print(f"  [2] Eliminar {len(ctrs)} contenedores detenidos")
    if vols: console.print(f"  [3] Eliminar {len(vols)} volúmenes huérfanos")
    console.print("  [A] Todo  |  ENTER=omitir")

    try: raw = console.input("  Elige: ").strip().upper()
    except: return
    if raw == "A" or "1" in raw:
        for i in imgs: _run(["docker", "rmi", "-f", i["id"]])
        console.print("  ✅ Imágenes eliminadas.")
    if raw == "A" or "2" in raw:
        for c in ctrs: _run(["docker", "rm", "-f", c["id"]])
        console.print("  ✅ Contenedores detenidos eliminados.")
    if raw == "A" or "3" in raw:
        for v in vols: _run(["docker", "volume", "rm", v["name"]])
        console.print("  ✅ Volúmenes huérfanos eliminados.")
