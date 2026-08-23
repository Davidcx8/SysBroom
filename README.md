<div align="center">

```
██        ██████  ██    ██  ██████  ████████  ████████   ███████   ███████  ██     ██ 
 ██      ██    ██  ██  ██  ██    ██ ██     ██ ██     ██ ██     ██ ██     ██ ███   ███ 
  ██     ██         ████   ██       ██     ██ ██     ██ ██     ██ ██     ██ ████ ████ 
   ██     ██████     ██     ██████  ████████  ████████  ██     ██ ██     ██ ██ ███ ██ 
  ██           ██    ██          ██ ██     ██ ██   ██   ██     ██ ██     ██ ██     ██ 
 ██      ██    ██    ██    ██    ██ ██     ██ ██    ██  ██     ██ ██     ██ ██     ██ 
██        ██████     ██     ██████  ████████  ██     ██  ███████   ███████  ██     ██ 
```

**v3.0.0** · Sistema de Limpieza Inteligente para Windows

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows)](https://www.microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

---

SysBroom es una herramienta de limpieza y diagnóstico de sistema para Windows. Analiza disco, aplicaciones, herramientas de IA, Docker, WSL y procesos — y te permite limpiar de forma segura, granular y con justificaciones claras sobre qué y por qué borrar.

## ✨ Características

| Módulo | Qué hace |
|--------|----------|
| 🪟 **Windows** | Temporales, Prefetch, Papelera, Windows Update, Thumbnails, Dumps, cachés de apps |
| 🤖 **IA** | Detecta Claude, Cursor, ChatGPT, Ollama, HuggingFace, Antigravity, Aider, LM Studio y más |
| 📦 **Apps** | Residuos de programas desinstalados, extensiones de navegador, venvs y node_modules huérfanos |
| 🐳 **Docker** | Imágenes, contenedores, volúmenes y redes — limpieza granular imagen por imagen |
| 🐧 **WSL** | Auditoría por distro: apt, /tmp, journals, VHDX compactación |
| ⚙️ **Procesos** | Zombies, procesos de alto consumo, puertos de desarrollo bloqueados |
| 📅 **Scheduler** | Limpieza automática programada vía Windows Task Scheduler |

## 🚀 Instalación rápida

### 1. Requisitos
- **Windows 10/11**
- **Python 3.9 o superior** — [descargar aquí](https://www.python.org/downloads/) *(marcar "Add Python to PATH")*

### 2. Clonar o descargar

```bash
git clone https://github.com/Davidcx8/SysBroom.git
cd SysBroom
```

O descarga el ZIP desde el botón verde **Code → Download ZIP** en GitHub.

### 3. Instalar dependencias (un clic)

Haz doble clic en **`install.bat`** — detecta Python, instala todo lo necesario y confirma que funciona.

O desde la terminal:

```bat
install.bat
```

> **¿No sabes qué es una dependencia?** No te preocupes. El `install.bat` lo hace todo solo.

### 4. Primer uso

```bat
sb scan
```

## 📖 Comandos

### Escaneo y limpieza general

```bat
sb                  # Asistente interactivo guiado por fases
sb scan             # Diagnóstico completo (solo lectura, sin borrar)
sb clean            # Limpieza automática según perfil configurado
sb dry              # Simular limpieza sin borrar nada (dry-run)
```

### Módulos dedicados

```bat
sb ai               # Auditoría de herramientas IA
sb apps             # Residuos de apps, extensiones, venvs, node_modules
sb docker           # Auditoría Docker granular
sb wsl              # Auditoría WSL por distro y componente
sb proc             # Procesos: zombies, CPU, RAM, puertos
```

### Programación automática

```bat
sb sched            # Configurar día, hora y categorías a limpiar
sb status           # Ver próxima ejecución y perfil activo
sb unsched          # Eliminar tarea programada
```

### Historial y reportes

```bat
sb history          # Últimas 10 limpiezas
sb report           # Ver último reporte generado
sb help             # Menú completo de comandos
```

## 🎛️ Menú interactivo — teclas rápidas

Cuando ejecutas `sb` o `sb clean` aparece el menú de selección:

| Tecla | Acción |
|-------|--------|
| `#` | Activar/desactivar categoría por número |
| `A` | Activar todas las seguras |
| `N` | Desactivar todas |
| `D` | Filtrar: solo Docker |
| `W` | Filtrar: solo WSL |
| `AI` | Filtrar: solo IA |
| `P` | Mostrar solo prioridad ALTA |
| `I#` | Ver detalle de la categoría N |
| `X` | Quitar filtro activo |
| `ENTER` | Confirmar y limpiar |
| `Q` | Salir sin limpiar |

## 🤖 Detección de herramientas IA

SysBroom detecta automáticamente cachés, modelos y sesiones de:

**Asistentes e IDEs:** Claude Desktop · ChatGPT app · Cursor · GitHub Copilot · Antigravity/AGY · Aider · Continue.dev · Codeium · OpenCode

**Modelos locales:** Ollama · LM Studio · Jan.ai · HuggingFace Hub (transformers/diffusers)

**Frameworks:** LangChain · ChromaDB

**Clasificación inteligente:**
- 🔴 **JUNK** — cachés expiradas, logs viejos → borrado directo
- 🟡 **REVISAR** — modelos, historiales → confirmación del usuario
- 🟢 **SAFE** — activo en últimas 24h → nunca tocado

> Las conversaciones de Antigravity son analizadas leyendo el `transcript.jsonl` — se evalúa actividad reciente, número de interacciones y antigüedad. Nunca se tocan las activas o recientes.

## 🛡️ Seguridad

- **Modo dry-run** (`sb dry`): simula sin borrar nada
- Categorías "no seguras" requieren confirmación individual
- Procesos del sistema protegidos (lsass, csrss, winlogon, etc.)
- Modelos de IA siempre requieren confirmación del usuario

## 📁 Estructura del proyecto

```
SysBroom/
├── sysbroom.py          # Entry point principal
├── sb.bat               # Launcher de comandos
├── install.bat          # Instalador de dependencias
├── scheduler.py         # Programación automática
├── requirements.txt     # Dependencias Python
├── config.json          # Perfil y programación (generado automáticamente)
├── cleaner/
│   ├── ai_audit.py      # Auditoría de herramientas IA
│   ├── apps_audit.py    # Auditoría de apps y residuos
│   ├── docker_audit.py  # Auditoría de Docker
│   ├── wsl_audit.py     # Auditoría de WSL
│   ├── phase1_scan.py   # Escaneo paralelo del sistema
│   ├── phase2_analyze.py# Análisis y categorización
│   ├── phase3_decide.py # Menú interactivo de selección
│   ├── phase4_clean.py  # Motor de limpieza
│   └── phase5_report.py # Generación de reportes
├── utils/
│   ├── safe_delete.py   # Borrado seguro
│   └── sizes.py         # Utilidades de tamaño
└── logs/                # Reportes generados (ignorado en git)
```

## ⚙️ Requisitos opcionales

| Herramienta | Para qué | Requerido |
|-------------|----------|-----------|
| Python 3.9+ | Ejecutar SysBroom | ✅ Sí |
| Docker Desktop | Auditoría Docker | Opcional |
| WSL | Auditoría WSL | Opcional |
| Git | Detectar repos viejos | Opcional |
| Permisos admin | Limpiar `C:\Windows\Temp`, Prefetch | Recomendado |

## 📄 Licencia

MIT — ver [LICENSE](LICENSE)

---

<div align="center">
<sub>Hecho con 🧹 y Python · Windows 10/11</sub>
</div>
