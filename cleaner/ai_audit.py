"""
cleaner/ai_audit.py  —  SysBroom v3.0
Auditoría inteligente de herramientas, cachés, modelos y sesiones de IA.

Clasificación de resultados:
  JUNK   — basura segura, borrado directo (caches expirados, logs viejos)
  REVIEW — revisar con el usuario (modelos, historiales, sesiones >30 días)
  SAFE   — excluido, nunca tocar (activo en últimas 24h, en uso)
"""
import os, json, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

LOCALAPP  = Path(os.environ.get("LOCALAPPDATA", ""))
APPDATA   = Path(os.environ.get("APPDATA", ""))
HOME      = Path.home()
NOW       = datetime.now(timezone.utc)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _size(path: Path) -> int:
    """Tamaño recursivo de un directorio o archivo."""
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
    """Días desde la última modificación de un path (archivo o dir más reciente)."""
    if not path.exists():
        return None
    try:
        if path.is_file():
            return (NOW - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)).days
        # Para directorios: buscar el archivo más reciente (hasta 3 niveles)
        newest = None
        for root, _, files in os.walk(path):
            depth = root.replace(str(path), "").count(os.sep)
            if depth > 3:
                continue
            for f in files:
                try:
                    mtime = Path(root, f).stat().st_mtime
                    if newest is None or mtime > newest:
                        newest = mtime
                except Exception:
                    pass
        if newest:
            return (NOW - datetime.fromtimestamp(newest, tz=timezone.utc)).days
        return None
    except Exception:
        return None

def _fmt_age(days: Optional[float]) -> str:
    if days is None:
        return "desconocido"
    if days == 0:
        return "hoy"
    if days == 1:
        return "ayer"
    if days < 7:
        return f"{int(days)} días"
    if days < 30:
        return f"{int(days // 7)} sem."
    if days < 365:
        return f"{int(days // 30)} mes(es)"
    return f"{int(days // 365)} año(s)"

def _entry(tool: str, path: Path, label: str, kind: str,
           size_bytes: int = 0, age_days: Optional[float] = None,
           reason: str = "", why_delete: str = "", extra: dict = None) -> dict:
    """Estructura estándar de un ítem detectado."""
    return {
        "tool": tool,
        "label": label,
        "path": str(path),
        "kind": kind,           # JUNK | REVIEW | SAFE
        "size_bytes": size_bytes,
        "age_days": age_days,
        "age_str": _fmt_age(age_days),
        "reason": reason,
        "why_delete": why_delete,
        "extra": extra or {},
    }

# ──────────────────────────────────────────────────────────────────────────────
# Análisis inteligente de conversaciones Antigravity
# ──────────────────────────────────────────────────────────────────────────────

def _analyze_agy_conversation(conv_dir: Path) -> Optional[dict]:
    """
    Analiza una carpeta de conversación de Antigravity brain.
    Lee el transcript.jsonl (si existe) para determinar:
      - Fecha de última interacción
      - Número de interacciones (pasos del usuario)
      - Si tiene actividad en las últimas 24h → SAFE (nunca tocar)
      - Si tiene actividad en los últimos 7 días → SAFE
      - Si inactiva >60 días con ≤3 interacciones → JUNK
      - Si inactiva >60 días con >3 interacciones → REVIEW
      - Resto → REVIEW
    """
    if not conv_dir.is_dir():
        return None

    log_dir = conv_dir / ".system_generated" / "logs"
    transcript = log_dir / "transcript.jsonl"
    size = _size(conv_dir)

    # Datos base desde el filesystem
    age = _age_days(conv_dir)
    last_active_str = "desconocido"
    user_turns = 0
    model_turns = 0
    conv_id = conv_dir.name

    # Intentar leer el transcript
    if transcript.exists():
        try:
            lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines:
                try:
                    step = json.loads(line)
                    src = step.get("source", "")
                    stype = step.get("type", "")
                    if stype == "USER_INPUT":
                        user_turns += 1
                    elif stype == "PLANNER_RESPONSE":
                        model_turns += 1
                    # Extraer timestamp del último paso
                    content = step.get("content", "")
                    # Buscar timestamps en el contenido (ISO format)
                    ts_match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", str(content))
                    if ts_match:
                        try:
                            last_active_str = ts_match.group(1)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    # Calcular edad real desde el filesystem si no pudimos del transcript
    total_turns = user_turns + model_turns

    # Clasificación inteligente
    if age is not None and age <= 1:
        # Activa en últimas 24h → NUNCA TOCAR
        kind = "SAFE"
        reason = f"Conversación activa (última actividad: {_fmt_age(age)})"
        why_delete = ""
    elif age is not None and age <= 7:
        # Activa en últimos 7 días
        kind = "SAFE"
        reason = f"Conversación reciente ({_fmt_age(age)}), {user_turns} mensajes del usuario"
        why_delete = ""
    elif age is not None and age > 60 and total_turns <= 3:
        # Muy vieja y poca actividad
        kind = "JUNK"
        reason = f"Conversación inactiva hace {_fmt_age(age)}, solo {total_turns} interacción(es)"
        why_delete = f"Sin actividad en {_fmt_age(age)}, conversación mínima ({total_turns} pasos). Residuo seguro."
    elif age is not None and age > 90:
        # Muy vieja aunque tenga más interacciones
        kind = "REVIEW"
        reason = f"Inactiva {_fmt_age(age)}, {user_turns} msgs usuario, {model_turns} respuestas"
        why_delete = f"Conversación de hace +3 meses. Verificar si es útil como referencia."
    elif age is not None and age > 30:
        kind = "REVIEW"
        reason = f"Inactiva {_fmt_age(age)}, {total_turns} interacciones totales"
        why_delete = f"Sin actividad en +30 días. Revisar si se necesita conservar."
    else:
        kind = "SAFE"
        reason = f"Activa ({_fmt_age(age)})"
        why_delete = ""

    return {
        "conv_id": conv_id,
        "path": str(conv_dir),
        "size_bytes": size,
        "age_days": age,
        "age_str": _fmt_age(age),
        "user_turns": user_turns,
        "model_turns": model_turns,
        "total_turns": total_turns,
        "last_active_str": last_active_str,
        "kind": kind,
        "reason": reason,
        "why_delete": why_delete,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Escáneres por herramienta
# ──────────────────────────────────────────────────────────────────────────────

def _scan_cursor() -> List[dict]:
    items = []
    roots = [
        APPDATA / "Cursor",
        LOCALAPP / "Cursor",
        LOCALAPP / "cursor-updater",
        LOCALAPP / "Programs" / "cursor",
    ]
    cache_dirs = [
        APPDATA / "Cursor" / "Cache",
        APPDATA / "Cursor" / "Code Cache",
        APPDATA / "Cursor" / "GPUCache",
        APPDATA / "Cursor" / "logs",
        LOCALAPP / "Cursor" / "Cache",
        LOCALAPP / "cursor-updater",
    ]
    for cd in cache_dirs:
        if cd.exists():
            sz = _size(cd)
            age = _age_days(cd)
            items.append(_entry(
                "Cursor", cd, f"Cursor — {cd.name}",
                kind="JUNK" if (age is not None and age > 3) else "REVIEW",
                size_bytes=sz, age_days=age,
                reason=f"Caché de Cursor IDE ({cd.name})",
                why_delete="Caché temporal del IDE, se regenera automáticamente."
            ))
    # Workspaces / semantic index
    ws = APPDATA / "Cursor" / "User" / "workspaceStorage"
    if ws.exists():
        sz = _size(ws)
        age = _age_days(ws)
        items.append(_entry(
            "Cursor", ws, "Cursor — Workspace Storage",
            kind="REVIEW",
            size_bytes=sz, age_days=age,
            reason="Índice semántico y estado de workspaces de Cursor",
            why_delete="Espacio de workspaces antiguos. Revisar antes de borrar."
        ))
    return items

def _scan_claude_desktop() -> List[dict]:
    items = []
    cache_dirs = [
        APPDATA / "Claude" / "Cache",
        APPDATA / "Claude" / "Code Cache",
        APPDATA / "Claude" / "GPUCache",
        APPDATA / "Claude" / "logs",
        LOCALAPP / "Claude" / "Cache",
        LOCALAPP / "AnthropicClaude" / "Cache",
    ]
    for cd in cache_dirs:
        if cd.exists():
            sz = _size(cd)
            age = _age_days(cd)
            items.append(_entry(
                "Claude Desktop", cd, f"Claude — {cd.name}",
                kind="JUNK" if (age is not None and age > 3) else "REVIEW",
                size_bytes=sz, age_days=age,
                reason=f"Caché de Claude Desktop ({cd.name})",
                why_delete="Caché del cliente de Claude. Se regenera al abrir la app."
            ))
    return items

def _scan_chatgpt_app() -> List[dict]:
    items = []
    cache_dirs = [
        APPDATA / "ChatGPT" / "Cache",
        APPDATA / "ChatGPT" / "Code Cache",
        APPDATA / "ChatGPT" / "GPUCache",
        APPDATA / "ChatGPT" / "logs",
        LOCALAPP / "OpenAI" / "ChatGPT" / "Cache",
    ]
    for cd in cache_dirs:
        if cd.exists():
            sz = _size(cd)
            age = _age_days(cd)
            items.append(_entry(
                "ChatGPT App", cd, f"ChatGPT — {cd.name}",
                kind="JUNK" if (age is not None and age > 3) else "REVIEW",
                size_bytes=sz, age_days=age,
                reason=f"Caché de app ChatGPT",
                why_delete="Caché temporal de la app de ChatGPT."
            ))
    return items

def _scan_github_copilot() -> List[dict]:
    items = []
    paths = [
        (APPDATA / "GitHub Copilot", "JUNK", "Caché de GitHub Copilot"),
        (HOME / ".github-copilot-agent", "REVIEW", "Agente local de Copilot"),
        (LOCALAPP / "GitHubCopilot", "JUNK", "Datos locales de Copilot"),
    ]
    for path, kind, label in paths:
        if path.exists():
            sz = _size(path)
            age = _age_days(path)
            items.append(_entry(
                "GitHub Copilot", path, label,
                kind=kind, size_bytes=sz, age_days=age,
                reason=label,
                why_delete="Datos residuales del asistente Copilot."
            ))
    return items

def _scan_antigravity() -> List[dict]:
    """Análisis inteligente de conversaciones de Antigravity."""
    items = []
    brain_dir = HOME / ".gemini" / "antigravity" / "brain"
    if not brain_dir.exists():
        return items

    conversations = []
    try:
        for conv_dir in brain_dir.iterdir():
            if conv_dir.is_dir() and not conv_dir.name.startswith("."):
                analysis = _analyze_agy_conversation(conv_dir)
                if analysis:
                    conversations.append(analysis)
    except Exception:
        pass

    # Agrupar: solo reportar JUNK y REVIEW como ítems individuales
    for conv in conversations:
        if conv["kind"] == "SAFE":
            continue
        items.append(_entry(
            "Antigravity / AGY",
            Path(conv["path"]),
            f"Conversación AGY — {conv['conv_id'][:16]}…",
            kind=conv["kind"],
            size_bytes=conv["size_bytes"],
            age_days=conv["age_days"],
            reason=conv["reason"],
            why_delete=conv["why_delete"],
            extra={
                "conv_id": conv["conv_id"],
                "user_turns": conv["user_turns"],
                "model_turns": conv["model_turns"],
                "last_active": conv["last_active_str"],
            }
        ))

    # También escanear caché general de antigravity
    cache_dir = HOME / ".gemini" / "antigravity" / "cache"
    if cache_dir.exists():
        sz = _size(cache_dir)
        age = _age_days(cache_dir)
        if sz > 0:
            items.append(_entry(
                "Antigravity / AGY", cache_dir, "AGY — Caché general",
                kind="JUNK" if (age is not None and age > 7) else "REVIEW",
                size_bytes=sz, age_days=age,
                reason="Caché temporal de Antigravity",
                why_delete="Caché temporal del agente. Se regenera automáticamente."
            ))

    return items

def _scan_aider() -> List[dict]:
    items = []
    paths = [
        (HOME / ".aider", "logs", "JUNK", "Logs de Aider", "Logs del asistente Aider."),
        (HOME / ".aider.chat.history.md", "file", "REVIEW", "Historial de chat Aider", "Historial de conversaciones con Aider. Revisar si ya no es necesario."),
        (HOME / ".aider.model.metadata.json", "file", "JUNK", "Metadatos de modelo Aider", "Archivo temporal de metadatos de Aider."),
        (HOME / ".aider.tags.cache.v3", "dir", "JUNK", "Caché de tags Aider", "Caché de análisis de código de Aider, se regenera."),
    ]
    for path, ptype, kind, label, why in paths:
        if path.exists():
            sz = _size(path)
            age = _age_days(path)
            if ptype == "file" and kind == "REVIEW" and age is not None and age <= 7:
                kind = "SAFE"
            items.append(_entry(
                "Aider", path, label,
                kind=kind, size_bytes=sz, age_days=age,
                reason=label, why_delete=why
            ))
    return items

def _scan_continue_dev() -> List[dict]:
    items = []
    paths = [
        (HOME / ".continue" / "logs", "JUNK", "Logs de Continue.dev"),
        (HOME / ".continue" / "index", "REVIEW", "Índice semántico de Continue.dev"),
        (HOME / ".continue" / "sessions", "REVIEW", "Sesiones de Continue.dev"),
    ]
    for path, kind, label in paths:
        if path.exists():
            sz = _size(path)
            age = _age_days(path)
            items.append(_entry(
                "Continue.dev", path, label,
                kind=kind, size_bytes=sz, age_days=age,
                reason=label,
                why_delete="Datos del asistente Continue.dev en VS Code/Cursor."
            ))
    return items

def _scan_codeium() -> List[dict]:
    items = []
    paths = [
        APPDATA / "Codeium",
        LOCALAPP / "Codeium",
    ]
    for p in paths:
        if p.exists():
            sz = _size(p)
            age = _age_days(p)
            items.append(_entry(
                "Codeium", p, f"Codeium — {p.name}",
                kind="REVIEW", size_bytes=sz, age_days=age,
                reason="Datos del asistente Codeium",
                why_delete="Caché y datos del plugin Codeium."
            ))
    return items

def _scan_opencode() -> List[dict]:
    items = []
    paths = [
        APPDATA / "opencode",
        LOCALAPP / "opencode",
        HOME / ".opencode",
    ]
    for p in paths:
        if p.exists():
            sz = _size(p)
            age = _age_days(p)
            items.append(_entry(
                "OpenCode", p, f"OpenCode — {p.name}",
                kind="REVIEW", size_bytes=sz, age_days=age,
                reason="Datos de OpenCode AI",
                why_delete="Caché y datos del asistente OpenCode."
            ))
    return items

# ──────────────────────────────────────────────────────────────────────────────
# Modelos locales
# ──────────────────────────────────────────────────────────────────────────────

def _scan_ollama_models() -> List[dict]:
    items = []
    ollama_dir = HOME / ".ollama"
    models_dir = ollama_dir / "models"
    if not models_dir.exists():
        return items

    # Buscar manifests para obtener nombre real
    manifests_dir = models_dir / "manifests"
    model_list = []
    if manifests_dir.exists():
        try:
            for registry in manifests_dir.iterdir():
                for namespace in registry.iterdir() if registry.is_dir() else []:
                    for model_name in namespace.iterdir() if namespace.is_dir() else []:
                        for tag in model_name.iterdir() if model_name.is_dir() else []:
                            full_name = f"{namespace.name}/{model_name.name}:{tag.name}"
                            age = _age_days(tag)
                            model_list.append({
                                "name": full_name,
                                "path": str(tag),
                                "age_days": age,
                                "age_str": _fmt_age(age),
                            })
        except Exception:
            pass

    # Tamaño total de blobs (los modelos reales)
    blobs_dir = models_dir / "blobs"
    total_sz = _size(blobs_dir) if blobs_dir.exists() else _size(models_dir)

    if total_sz > 0 or model_list:
        items.append(_entry(
            "Ollama", models_dir, "Ollama — Modelos locales",
            kind="REVIEW",
            size_bytes=total_sz,
            age_days=_age_days(models_dir),
            reason=f"{len(model_list)} modelo(s) instalado(s)" if model_list else "Directorio de modelos Ollama",
            why_delete="Modelos de lenguaje locales. Eliminar los que ya no uses para recuperar espacio.",
            extra={"models": model_list}
        ))
    return items

def _scan_lm_studio() -> List[dict]:
    items = []
    paths = [
        HOME / ".cache" / "lm-studio" / "models",
        HOME / ".lmstudio" / "models",
    ]
    for models_dir in paths:
        if models_dir.exists():
            sz = _size(models_dir)
            age = _age_days(models_dir)
            if sz > 0:
                items.append(_entry(
                    "LM Studio", models_dir, "LM Studio — Modelos locales",
                    kind="REVIEW",
                    size_bytes=sz, age_days=age,
                    reason="Modelos GGUF descargados en LM Studio",
                    why_delete="Modelos de LM Studio. Eliminar los que ya no uses."
                ))
    return items

def _scan_jan_ai() -> List[dict]:
    items = []
    models_dir = HOME / "jan" / "models"
    if models_dir.exists():
        sz = _size(models_dir)
        age = _age_days(models_dir)
        if sz > 0:
            items.append(_entry(
                "Jan.ai", models_dir, "Jan.ai — Modelos locales",
                kind="REVIEW",
                size_bytes=sz, age_days=age,
                reason="Modelos descargados en Jan.ai",
                why_delete="Modelos de Jan.ai. Eliminar los que ya no uses."
            ))
    return items

def _scan_huggingface() -> List[dict]:
    items = []
    hub_dir = HOME / ".cache" / "huggingface" / "hub"
    if not hub_dir.exists():
        return items
    sz = _size(hub_dir)
    age = _age_days(hub_dir)
    if sz == 0:
        return items

    # Listar repos/modelos descargados
    model_list = []
    try:
        for repo_dir in hub_dir.iterdir():
            if repo_dir.is_dir() and repo_dir.name.startswith("models--"):
                name = repo_dir.name.replace("models--", "").replace("--", "/")
                repo_sz = _size(repo_dir)
                repo_age = _age_days(repo_dir)
                model_list.append({
                    "name": name,
                    "size_bytes": repo_sz,
                    "age_days": repo_age,
                    "age_str": _fmt_age(repo_age),
                })
    except Exception:
        pass

    items.append(_entry(
        "HuggingFace", hub_dir, "HuggingFace Hub — Modelos cacheados",
        kind="REVIEW",
        size_bytes=sz, age_days=age,
        reason=f"{len(model_list)} modelo(s) en caché de transformers/diffusers",
        why_delete="Modelos de HuggingFace descargados. Limpiar los que ya no uses.",
        extra={"models": model_list}
    ))
    return items

def _scan_langchain_cache() -> List[dict]:
    items = []
    paths = [
        HOME / ".langchain",
        LOCALAPP / "langchain",
    ]
    for p in paths:
        if p.exists():
            sz = _size(p)
            age = _age_days(p)
            if sz > 0:
                items.append(_entry(
                    "LangChain", p, "LangChain — Caché",
                    kind="JUNK" if (age is not None and age > 7) else "REVIEW",
                    size_bytes=sz, age_days=age,
                    reason="Caché de LangChain (SQLite de respuestas LLM)",
                    why_delete="Caché de llamadas LLM de LangChain. Seguro borrar si no necesitas respuestas cacheadas."
                ))
    return items

def _scan_chroma_faiss() -> List[dict]:
    """Detecta bases de datos vectoriales huérfanas comunes."""
    items = []
    # Buscar en lugares típicos de desarrollo
    search_roots = [
        HOME / "Desktop",
        HOME / "Documents",
        HOME / "source",
        HOME / "projects",
        HOME / "dev",
    ]
    chroma_dirs = []
    for root in search_roots:
        if not root.exists():
            continue
        try:
            for p in root.rglob(".chroma"):
                if p.is_dir():
                    chroma_dirs.append(p)
            for p in root.rglob("chroma_db"):
                if p.is_dir():
                    chroma_dirs.append(p)
        except Exception:
            pass

    for cd in chroma_dirs[:10]:  # máx 10 para no spamear
        sz = _size(cd)
        age = _age_days(cd)
        parent_age = _age_days(cd.parent)
        # Solo reportar si el proyecto padre parece abandonado
        effective_age = parent_age if parent_age is not None else age
        if effective_age is not None and effective_age > 30:
            items.append(_entry(
                "ChromaDB", cd, f"ChromaDB — {cd.parent.name}/{cd.name}",
                kind="REVIEW",
                size_bytes=sz, age_days=age,
                reason=f"Base de datos vectorial en proyecto inactivo ({_fmt_age(effective_age)})",
                why_delete="Vector store de proyecto aparentemente inactivo. Verificar antes de borrar."
            ))

    return items

# ──────────────────────────────────────────────────────────────────────────────
# Función principal de auditoría
# ──────────────────────────────────────────────────────────────────────────────

def ai_scan_all(console=None) -> Dict[str, Any]:
    """
    Escanea todas las herramientas IA conocidas y retorna un diccionario
    estructurado con ítems clasificados por kind: JUNK / REVIEW / SAFE.
    """
    def log(msg: str):
        if console:
            try:
                console.log(f"[dim]{msg}[/dim]")
            except Exception:
                pass

    all_items: List[dict] = []
    scanners = [
        ("Cursor IDE...", _scan_cursor),
        ("Claude Desktop...", _scan_claude_desktop),
        ("ChatGPT App...", _scan_chatgpt_app),
        ("GitHub Copilot...", _scan_github_copilot),
        ("Antigravity/AGY...", _scan_antigravity),
        ("Aider...", _scan_aider),
        ("Continue.dev...", _scan_continue_dev),
        ("Codeium...", _scan_codeium),
        ("OpenCode...", _scan_opencode),
        ("Ollama (modelos)...", _scan_ollama_models),
        ("LM Studio (modelos)...", _scan_lm_studio),
        ("Jan.ai (modelos)...", _scan_jan_ai),
        ("HuggingFace Hub...", _scan_huggingface),
        ("LangChain caché...", _scan_langchain_cache),
        ("ChromaDB/FAISS...", _scan_chroma_faiss),
    ]

    for msg, fn in scanners:
        log(f"IA: {msg}")
        try:
            items = fn()
            all_items.extend(items)
        except Exception as e:
            if console:
                try:
                    console.log(f"[dim yellow]  ⚠ {msg} → {e}[/dim yellow]")
                except Exception:
                    pass

    # Estadísticas
    junk_items  = [i for i in all_items if i["kind"] == "JUNK"]
    review_items = [i for i in all_items if i["kind"] == "REVIEW"]
    safe_items  = [i for i in all_items if i["kind"] == "SAFE"]

    junk_bytes   = sum(i["size_bytes"] for i in junk_items)
    review_bytes = sum(i["size_bytes"] for i in review_items)

    return {
        "available": True,
        "items": all_items,
        "junk": junk_items,
        "review": review_items,
        "safe": safe_items,
        "junk_bytes": junk_bytes,
        "review_bytes": review_bytes,
        "total_bytes": junk_bytes + review_bytes,
        "tools_found": list({i["tool"] for i in all_items}),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Reporte y limpieza interactiva
# ──────────────────────────────────────────────────────────────────────────────

def show_ai_report(data: Dict[str, Any], console) -> None:
    """Muestra el reporte completo de auditoría IA con tablas rich."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.rule import Rule
    from rich import box
    from utils.sizes import format_size

    if not data.get("available"):
        console.print("[yellow]No se detectaron herramientas IA instaladas.[/]")
        return

    tools = data.get("tools_found", [])
    junk  = data.get("junk", [])
    rev   = data.get("review", [])

    console.print(Panel(
        f"  🤖 Herramientas detectadas:    [bold white]{len(tools)}[/]\n"
        f"  🔴 Basura segura (JUNK):       [bold white]{len(junk)}[/] ítems "
        f"· [bold red]{format_size(data['junk_bytes'])}[/]\n"
        f"  🟡 Para revisar (REVIEW):      [bold white]{len(rev)}[/] ítems "
        f"· [bold yellow]{format_size(data['review_bytes'])}[/]\n"
        f"  📌 Herramientas: [dim]{', '.join(tools) if tools else 'Ninguna'}[/]",
        title="🤖 [bold white]IA — Auditoría de Herramientas y Modelos[/]",
        border_style="magenta", padding=(1, 3)
    ))

    def _table(items: List[dict], title: str, color: str):
        if not items:
            return
        console.print(Rule(f"[bold {color}]{title}[/]", style=color))
        t = Table(box=box.ROUNDED, border_style=color,
                  header_style=f"bold {color}", min_width=100)
        t.add_column("Herramienta", width=18)
        t.add_column("Ítem", min_width=32)
        t.add_column("Tamaño", width=11, justify="right")
        t.add_column("Inactivo", width=12, justify="center")
        t.add_column("¿Por qué borrar?", min_width=28, style="dim")
        for item in sorted(items, key=lambda x: -x["size_bytes"]):
            sz = item["size_bytes"]
            sc = "red" if sz > 500*1024**2 else "yellow" if sz > 50*1024**2 else "white"
            t.add_row(
                f"[bold]{item['tool']}[/]",
                item["label"],
                f"[{sc}]{format_size(sz)}[/]" if sz > 0 else "[dim]—[/]",
                item["age_str"],
                item.get("why_delete", item.get("reason", ""))[:60],
            )
        console.print(t)

    _table(junk,  "🔴 BASURA SEGURA — Eliminación directa recomendada", "red")
    _table(rev,   "🟡 REVISAR — Confirmar antes de eliminar", "yellow")


def interactive_ai_cleanup(data: Dict[str, Any], console, dry_run: bool = False) -> Dict:
    """Limpieza interactiva granular de herramientas IA."""
    import shutil
    from utils.sizes import format_size
    from utils.safe_delete import safe_delete_dir_contents, safe_delete_dir, safe_delete_file
    from rich.panel import Panel

    report = {"deleted": [], "skipped": [], "errors": [], "freed_bytes": 0}
    junk  = data.get("junk", [])
    review = data.get("review", [])

    if not junk and not review:
        console.print("[green]✅ No se encontró basura de herramientas IA.[/]")
        return report

    # ── BASURA DIRECTA (JUNK) ──
    if junk:
        junk_bytes = sum(i["size_bytes"] for i in junk)
        console.print(Panel(
            f"🔴 [bold red]{len(junk)} ítems de basura segura[/] — "
            f"[bold]{format_size(junk_bytes)}[/]\n"
            f"[dim]Estas cachés y logs se regeneran automáticamente.[/]",
            border_style="red"
        ))
        ans = input("  ¿Eliminar toda la basura segura de IA? (s/N/ver): ").strip().lower()
        if ans == "ver":
            for i, item in enumerate(junk, 1):
                console.print(f"  [{i}] {item['tool']} — {item['label']} ({format_size(item['size_bytes'])})")
            idxs = input("  Números a borrar (ej: 1,3,5 o ENTER=todos s/N): ").strip()
            if idxs:
                try:
                    selected_junk = [junk[int(x)-1] for x in idxs.split(",") if x.strip().isdigit()]
                except Exception:
                    selected_junk = []
            else:
                selected_junk = []
            ans2 = input("  ¿Confirmar selección? (s/N): ").strip().lower()
            if ans2 == "s":
                ans = "s"
                junk = selected_junk
            else:
                ans = "n"

        if ans == "s":
            for item in junk:
                p = Path(item["path"])
                try:
                    if dry_run:
                        console.print(f"  [dim][DRY-RUN] Omitido: {item['label']}[/]")
                        report["skipped"].append(item["path"])
                    elif p.is_file():
                        ok, err = safe_delete_file(p)
                        if ok:
                            report["deleted"].append(item["path"])
                            report["freed_bytes"] += item["size_bytes"]
                            console.print(f"  ✅ {item['label']} — [green]{format_size(item['size_bytes'])}[/]")
                        else:
                            report["errors"].append(err)
                    elif p.is_dir():
                        ok, err = safe_delete_dir_contents(p)
                        report["deleted"].append(item["path"])
                        report["freed_bytes"] += item["size_bytes"]
                        console.print(f"  ✅ {item['label']} — [green]{format_size(item['size_bytes'])}[/]")
                except Exception as e:
                    report["errors"].append(str(e))

    # ── REVISIÓN INDIVIDUAL ──
    if review:
        console.print(f"\n  🟡 [bold yellow]{len(review)} ítems para revisar:[/]")
        for item in sorted(review, key=lambda x: -x["size_bytes"]):
            sz = format_size(item["size_bytes"])
            console.print(
                f"\n  [bold]{item['tool']}[/] — {item['label']}\n"
                f"  [dim]Ruta: {item['path'][:70]}[/]\n"
                f"  [dim]Tamaño: {sz} · Inactivo: {item['age_str']}[/]\n"
                f"  [dim italic]{item.get('why_delete', '')}[/]"
            )
            # Mostrar modelos internos si los hay
            models = item.get("extra", {}).get("models", [])
            if models:
                console.print(f"  [dim]Modelos ({len(models)}):[/]")
                for m in models[:5]:
                    name = m.get("name", "?")
                    msz = format_size(m.get("size_bytes", 0)) if m.get("size_bytes") else ""
                    age = m.get("age_str", "")
                    console.print(f"    · [cyan]{name}[/] {msz} {age}")
                if len(models) > 5:
                    console.print(f"    [dim]... y {len(models)-5} más[/]")

            ans = input(f"  ¿Eliminar? (s/N): ").strip().lower()
            if ans == "s":
                p = Path(item["path"])
                try:
                    if dry_run:
                        console.print(f"  [dim][DRY-RUN] Omitido[/]")
                        report["skipped"].append(item["path"])
                    elif p.is_file():
                        ok, err = safe_delete_file(p)
                        if ok:
                            report["deleted"].append(item["path"])
                            report["freed_bytes"] += item["size_bytes"]
                            console.print(f"  ✅ Eliminado — [green]{format_size(item['size_bytes'])}[/]")
                        else:
                            report["errors"].append(err)
                    elif p.is_dir():
                        safe_delete_dir_contents(p)
                        report["deleted"].append(item["path"])
                        report["freed_bytes"] += item["size_bytes"]
                        console.print(f"  ✅ Eliminado — [green]{format_size(item['size_bytes'])}[/]")
                except Exception as e:
                    report["errors"].append(str(e))
            else:
                report["skipped"].append(item["path"])
                console.print("  [dim]→ Conservado[/]")

    return report
