from typing import Dict, Any
from utils.sizes import format_size

# Prioridad: ALTA > MEDIA > BAJA
PRIORITY_ORDER = {"ALTA": 0, "MEDIA": 1, "BAJA": 2}

def _priority(size_bytes: int, base: str, big_thresh: int = 500*1024**2) -> str:
    if size_bytes > big_thresh:
        return "ALTA"
    if size_bytes > 50*1024**2:
        return "MEDIA"
    return base

def analyze(scan: Dict[str, Any]) -> Dict[str, Any]:
    cats = []

    def add(id, name, emoji, priority, size, details, safe=True,
            enabled=True, meta=None, why_delete: str = ""):
        cats.append({
            "id": id, "name": name, "emoji": emoji,
            "priority": priority, "size_bytes": size,
            "details": details, "safe": safe, "enabled": enabled,
            "meta": meta or {}, "why_delete": why_delete,
        })

    # ── Windows core ──────────────────────────────────────────────────────────
    wt = scan.get("windows_temp", {})
    if wt.get("size_bytes", 0) > 0 or wt.get("exists"):
        add("windows_temp", "Temporales del Usuario (%TEMP%)", "🗂️",
            _priority(wt.get("size_bytes", 0), "ALTA"),
            wt.get("size_bytes", 0),
            f"{wt.get('file_count', 0):,} archivos · {wt.get('path', '')}",
            why_delete=wt.get("why_delete", "Archivos temporales del usuario. Seguros de borrar."))

    st = scan.get("system_temp", {})
    if st.get("size_bytes", 0) > 0 or st.get("exists"):
        add("system_temp", "Temp del Sistema (C:\\Windows\\Temp)", "💻",
            _priority(st.get("size_bytes", 0), "ALTA"),
            st.get("size_bytes", 0),
            f"{st.get('file_count', 0):,} archivos · requiere admin",
            why_delete=st.get("why_delete", "Temporales del sistema. Se acumulan tras instalaciones."))

    pf = scan.get("prefetch", {})
    if pf.get("size_bytes", 0) > 0:
        add("prefetch", "Prefetch de Windows", "⚡", "MEDIA",
            pf.get("size_bytes", 0),
            f"{pf.get('file_count', 0):,} archivos · se regeneran automáticamente",
            why_delete=pf.get("why_delete", "Windows los regenera automáticamente."))

    rb = scan.get("recycle_bin", {})
    rb_sz = rb.get("size_bytes", 0)
    add("recycle_bin", "Papelera de Reciclaje", "♻️",
        "ALTA" if rb_sz > 100*1024**2 else "MEDIA",
        rb_sz, "Vaciar papelera de reciclaje",
        why_delete=rb.get("why_delete", "Archivos que ya elegiste eliminar, aún ocupan disco."))

    wu = scan.get("windows_update", {})
    wu_sz = wu.get("size_bytes", 0)
    if wu_sz > 0:
        add("windows_update", "Caché de Windows Update", "🔄",
            "ALTA" if wu_sz > 500*1024**2 else "MEDIA",
            wu_sz, "Archivos de actualización descargados (seguros de eliminar)",
            why_delete=wu.get("why_delete", "Paquetes ya instalados. Windows no los necesita."))

    th = scan.get("thumbnails", {})
    if th.get("size_bytes", 0) > 0:
        add("thumbnails", "Caché de Miniaturas (Thumbnails)", "🖼️", "BAJA",
            th.get("size_bytes", 0),
            f"{len(th.get('files', []))} archivos thumbcache",
            why_delete=th.get("why_delete", "Se regenera al abrir carpetas de imágenes."))

    dm = scan.get("dump_files", {})
    if dm.get("count", 0) > 0:
        add("dump_files", "Archivos de Volcado (.dmp / .mdmp)", "💥", "MEDIA",
            dm.get("size_bytes", 0),
            f"{dm.get('count', 0)} archivos de crash",
            why_delete=dm.get("why_delete", "Volcados de memoria de errores. Seguros si ya fueron analizados."))

    # ── App cache ─────────────────────────────────────────────────────────────
    ac_raw = scan.get("app_cache", {})
    ac = ac_raw.get("caches", ac_raw)  # compatibilidad con estructura nueva y vieja
    if isinstance(ac, dict):
        total_app = sum(v["size_bytes"] for v in ac.values() if isinstance(v, dict))
        if total_app > 0:
            apps = ", ".join(ac.keys())
            add("app_cache", "Caché de Aplicaciones", "📦",
                "ALTA" if total_app > 500*1024**2 else "MEDIA",
                total_app, f"{apps}",
                meta={"apps": ac},
                why_delete=ac_raw.get("why_delete", "Cachés de apps y navegadores. Se regeneran automáticamente."))

    # ── Docker ────────────────────────────────────────────────────────────────
    dk = scan.get("docker", {})
    if dk.get("available") and not dk.get("error"):
        d = len(dk.get("dangling_images", []))
        s = len(dk.get("stopped_containers", []))
        v = len(dk.get("volumes", []))
        if d + s + v > 0 or dk.get("build_cache_bytes", 0) > 0:
            parts = []
            if d: parts.append(f"{d} imágenes huérfanas")
            if s: parts.append(f"{s} contenedores detenidos")
            if v: parts.append(f"{v} volúmenes")
            if dk.get("build_cache_bytes", 0): parts.append("build cache")
            add("docker", "Docker — Limpieza General", "🐳",
                "ALTA" if dk.get("total_size_bytes", 0) > 200*1024**2 else "MEDIA",
                dk.get("total_size_bytes", 0), ", ".join(parts),
                why_delete=dk.get("why_delete", "Imágenes y contenedores Docker sin uso activo."))

    # ── WSL ───────────────────────────────────────────────────────────────────
    wsl = scan.get("wsl", {})
    if wsl.get("available") and wsl.get("tmp_size_bytes", 0) > 0:
        add("wsl", "WSL — Limpieza de /tmp", "🐧", "MEDIA",
            wsl.get("tmp_size_bytes", 0),
            f"Distros: {', '.join(wsl.get('distros', [])[:3])}",
            why_delete=wsl.get("why_delete", "Archivos temporales dentro de WSL."))

    # ── IA ────────────────────────────────────────────────────────────────────
    ai = scan.get("ai", {})
    if ai:
        ai_junk_bytes   = ai.get("junk_bytes", 0)
        ai_review_bytes = ai.get("review_bytes", 0)
        tools_found     = ai.get("tools_found", [])
        if ai_junk_bytes + ai_review_bytes > 0:
            parts = []
            if ai_junk_bytes:   parts.append(f"basura: {format_size(ai_junk_bytes)}")
            if ai_review_bytes: parts.append(f"revisar: {format_size(ai_review_bytes)}")
            add("ai_tools", "Herramientas de IA — Cachés y Residuos", "🤖",
                "ALTA" if ai_junk_bytes > 200*1024**2 else "MEDIA",
                ai_junk_bytes,
                f"{', '.join(tools_found[:4])}{'…' if len(tools_found) > 4 else ''}",
                safe=True, enabled=True,
                meta={"ai_data": ai},
                why_delete="Cachés y logs expirados de Claude, Cursor, ChatGPT, Aider, etc.")

        # Modelos locales → categoría separada REVIEW
        model_bytes = sum(
            i.get("size_bytes", 0)
            for i in ai.get("review", [])
            if "model" in i.get("label", "").lower() or i.get("tool") in
               ("Ollama", "LM Studio", "Jan.ai", "HuggingFace")
        )
        if model_bytes > 0:
            model_tools = list({
                i["tool"] for i in ai.get("review", [])
                if i.get("tool") in ("Ollama", "LM Studio", "Jan.ai", "HuggingFace")
            })
            add("ai_models", "Modelos IA Locales — Revisar y eliminar", "🧠",
                "MEDIA", model_bytes,
                f"{', '.join(model_tools)} — revisar modelos sin uso",
                safe=False, enabled=False,
                meta={"ai_data": ai},
                why_delete="Modelos de lenguaje locales. Pueden ocupar varios GB. Elimina los que ya no uses.")

    # ── Apps y residuos ───────────────────────────────────────────────────────
    apps_data = scan.get("apps", {})
    if apps_data:
        res_bytes  = apps_data.get("total_residues_bytes", 0)
        ext_bytes  = apps_data.get("total_extensions_bytes", 0)
        venv_bytes = apps_data.get("total_venv_bytes", 0)
        nm_bytes   = apps_data.get("total_nm_bytes", 0)
        cache_bytes = apps_data.get("total_cache_bytes", 0)
        total_apps  = res_bytes + ext_bytes + venv_bytes + nm_bytes + cache_bytes

        if total_apps > 0:
            parts = []
            if res_bytes:   parts.append(f"{format_size(res_bytes)} residuos")
            if venv_bytes:  parts.append(f"{format_size(venv_bytes)} venvs")
            if nm_bytes:    parts.append(f"{format_size(nm_bytes)} node_modules")
            if cache_bytes: parts.append(f"{format_size(cache_bytes)} cachés dev")

            add("app_residues", "Apps — Residuos y Entornos Huérfanos", "📦",
                "ALTA" if total_apps > 500*1024**2 else "MEDIA",
                total_apps, ", ".join(parts),
                safe=False, enabled=False,
                meta={"apps_data": apps_data},
                why_delete="Residuos de desinstalaciones, venvs y node_modules huérfanos.")

    # ── Proyectos git viejos ──────────────────────────────────────────────────
    op = scan.get("old_projects", {})
    if op.get("count", 0) > 0:
        add("old_projects", "Proyectos Git Sin Actividad (+6 meses)", "📁", "BAJA",
            op.get("total_size_bytes", 0),
            f"{op.get('count', 0)} repositorios · ⚠️ Requiere confirmación individual",
            safe=False, enabled=False,
            meta={"repos": op.get("repos", [])},
            why_delete=op.get("why_delete", "Repositorios sin commits en más de 6 meses."))

    # ── DNS ───────────────────────────────────────────────────────────────────
    add("dns_cache", "Caché DNS del Sistema", "🌐", "BAJA", 0,
        "ipconfig /flushdns — mejora rendimiento de red",
        why_delete="Fuerza resolución DNS fresca. Mejora conectividad si hay problemas de red.")

    # Ordenar ALTA → MEDIA → BAJA → tamaño desc
    cats.sort(key=lambda c: (PRIORITY_ORDER.get(c["priority"], 9), -c["size_bytes"]))

    total = sum(c["size_bytes"] for c in cats if c.get("enabled"))
    return {
        "categories": cats,
        "total_recoverable_bytes": total,
        "docker_available": dk.get("available", False) if "dk" in dir() else False,
        "wsl_available": wsl.get("available", False),
        "app_cache_detail": ac if isinstance(ac, dict) else {},
        "ai_available": bool(scan.get("ai", {}).get("tools_found")),
    }
