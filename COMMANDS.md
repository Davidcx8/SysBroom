# 📖 SysBroom v3.0 — Referencia Rápida de Comandos

## Escaneo y Limpieza General

| Comando | Función |
|---|---|
| `sb` | Asistente interactivo guiado por fases (scan + decide + clean + report) |
| `sb scan` | Diagnóstico completo (Windows, Docker, WSL, IA, Apps, Procesos). Solo lectura. |
| `sb clean` | Limpieza automática según el perfil configurado. |
| `sb dry` | **Simulación sin borrar** — muestra todo lo que se limpiaría. |

## Módulos Dedicados

| Comando | Función |
|---|---|
| `sb ai` | Auditoría de herramientas IA: Claude, Cursor, ChatGPT, Ollama, HuggingFace, AGY, Aider, etc. |
| `sb apps` | Residuos de programas desinstalados, extensiones desactivadas, venvs/node_modules huérfanos. |
| `sb docker` | Auditoría Docker granular: imagen por imagen, contenedores, volúmenes, redes. |
| `sb wsl` | Auditoría WSL: por distro y componente (apt, tmp, journal, conda, pip, VHDX). |
| `sb proc` | Detección de zombies, procesos pesados y liberación de puertos de desarrollo. |

## Programación

| Comando | Función |
|---|---|
| `sb sched` | Asistente para elegir día, hora y qué limpiar automáticamente. |
| `sb status` | Ver estado de la tarea en Windows y próxima ejecución. |
| `sb unsched` | Eliminar la tarea programada de Windows. |

## Historial y Reportes

| Comando | Función |
|---|---|
| `sb history` | Historial de limpiezas anteriores (últimas 10). |
| `sb report` | Ver el último reporte generado en la terminal. |
| `sb version` | Mostrar versión actual. |
| `sb help` | Menú de ayuda completo. |

## Atajos y Alias

| Alias | Equivalente |
|---|---|
| `sb check` | `sb scan` |
| `sb auto` | `sb clean` |
| `sb dryrun` | `sb dry` |
| `sb ia` | `sb ai` |
| `sb dk` | `sb docker` |
| `sb ports` | `sb proc` |
| `sb kill` | `sb proc` |
| `sb log` | `sb history` |
| `sb last` | `sb report` |
| `sb st` | `sb status` |

## Menú Interactivo — Teclas Rápidas

Cuando estás en el menú de selección de limpieza (`sb` o `sb clean`):

| Tecla | Acción |
|---|---|
| `#` | Activar/desactivar categoría por número |
| `A` | Activar todas las seguras |
| `N` | Desactivar todas |
| `D` | Filtrar: solo Docker |
| `W` | Filtrar: solo WSL |
| `AI` | Filtrar: solo IA |
| `P` | Filtrar: solo prioridad ALTA |
| `X` | Quitar filtro activo |
| `I#` | Ver detalle de la categoría #N |
| `ENTER` | Confirmar selección y limpiar |
| `Q` | Salir sin limpiar |