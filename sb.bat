@echo off
SETLOCAL EnableDelayedExpansion
chcp 65001 > nul 2>&1
SET "SCRIPT=%~dp0sysbroom.py"

REM -- Enrutar comandos ---------------------------------------------------------
IF "%~1"==""           ( python "%SCRIPT%"                          & GOTO :END )
IF /I "%~1"=="help"    GOTO :HELP
IF /I "%~1"=="h"       GOTO :HELP
IF /I "%~1"=="?"       GOTO :HELP
IF /I "%~1"=="aliases" GOTO :ALIASES
IF /I "%~1"=="al"      GOTO :ALIASES

REM -- Escaneo ------------------------------------------------------------------
IF /I "%~1"=="scan"     ( python "%SCRIPT%" --scan-only            & GOTO :END )
IF /I "%~1"=="check"    ( python "%SCRIPT%" --scan-only            & GOTO :END )
IF /I "%~1"=="s"        ( python "%SCRIPT%" --scan-only            & GOTO :END )

REM -- Limpieza -----------------------------------------------------------------
IF /I "%~1"=="clean"    ( python "%SCRIPT%" --auto                 & GOTO :END )
IF /I "%~1"=="auto"     ( python "%SCRIPT%" --auto                 & GOTO :END )
IF /I "%~1"=="c"        ( python "%SCRIPT%" --auto                 & GOTO :END )

REM -- Simulacion ---------------------------------------------------------------
IF /I "%~1"=="dry"      ( python "%SCRIPT%" --dry-run              & GOTO :END )
IF /I "%~1"=="dryrun"   ( python "%SCRIPT%" --dry-run              & GOTO :END )
IF /I "%~1"=="simulate" ( python "%SCRIPT%" --dry-run              & GOTO :END )
IF /I "%~1"=="sim"      ( python "%SCRIPT%" --dry-run              & GOTO :END )

REM -- Modulos dedicados --------------------------------------------------------
IF /I "%~1"=="docker"   ( python "%SCRIPT%" --docker               & GOTO :END )
IF /I "%~1"=="dk"       ( python "%SCRIPT%" --docker               & GOTO :END )
IF /I "%~1"=="d"        ( python "%SCRIPT%" --docker               & GOTO :END )

IF /I "%~1"=="wsl"      ( python "%SCRIPT%" --wsl                  & GOTO :END )
IF /I "%~1"=="w"        ( python "%SCRIPT%" --wsl                  & GOTO :END )

IF /I "%~1"=="ai"       ( python "%SCRIPT%" --ai                   & GOTO :END )
IF /I "%~1"=="ia"       ( python "%SCRIPT%" --ai                   & GOTO :END )
IF /I "%~1"=="a"        ( python "%SCRIPT%" --ai                   & GOTO :END )

IF /I "%~1"=="apps"     ( python "%SCRIPT%" --apps                 & GOTO :END )
IF /I "%~1"=="app"      ( python "%SCRIPT%" --apps                 & GOTO :END )
IF /I "%~1"=="ap"       ( python "%SCRIPT%" --apps                 & GOTO :END )

IF /I "%~1"=="proc"     ( python "%SCRIPT%" --processes            & GOTO :END )
IF /I "%~1"=="ports"    ( python "%SCRIPT%" --processes            & GOTO :END )
IF /I "%~1"=="kill"     ( python "%SCRIPT%" --processes            & GOTO :END )
IF /I "%~1"=="p"        ( python "%SCRIPT%" --processes            & GOTO :END )

REM -- Programacion -------------------------------------------------------------
IF /I "%~1"=="sched"    ( python "%SCRIPT%" --schedule             & GOTO :END )
IF /I "%~1"=="schedule" ( python "%SCRIPT%" --schedule             & GOTO :END )
IF /I "%~1"=="sch"      ( python "%SCRIPT%" --schedule             & GOTO :END )
IF /I "%~1"=="sc"       ( python "%SCRIPT%" --schedule             & GOTO :END )

IF /I "%~1"=="status"   ( python "%SCRIPT%" --status               & GOTO :END )
IF /I "%~1"=="st"       ( python "%SCRIPT%" --status               & GOTO :END )

IF /I "%~1"=="unsched"  ( python "%SCRIPT%" --unschedule           & GOTO :END )
IF /I "%~1"=="un"       ( python "%SCRIPT%" --unschedule           & GOTO :END )
IF /I "%~1"=="us"       ( python "%SCRIPT%" --unschedule           & GOTO :END )

REM -- Historial y reportes -----------------------------------------------------
IF /I "%~1"=="history"  ( python "%SCRIPT%" --history              & GOTO :END )
IF /I "%~1"=="log"      ( python "%SCRIPT%" --history              & GOTO :END )
IF /I "%~1"=="hi"       ( python "%SCRIPT%" --history              & GOTO :END )
IF /I "%~1"=="hs"       ( python "%SCRIPT%" --history              & GOTO :END )

IF /I "%~1"=="report"   ( python "%SCRIPT%" --report               & GOTO :END )
IF /I "%~1"=="last"     ( python "%SCRIPT%" --report               & GOTO :END )
IF /I "%~1"=="r"        ( python "%SCRIPT%" --report               & GOTO :END )
IF /I "%~1"=="rp"       ( python "%SCRIPT%" --report               & GOTO :END )

IF /I "%~1"=="version"  ( python "%SCRIPT%" --version              & GOTO :END )
IF /I "%~1"=="v"        ( python "%SCRIPT%" --version              & GOTO :END )

echo.
echo  +======================================================================+
echo  ^|  [SysBroom] Comando no reconocido: "%~1"
echo  ^|  Escribe  sb help  para ver todos los comandos disponibles.        ^|
echo  +======================================================================+
echo.
GOTO :END

:HELP
echo.
echo  +======================================================================+
echo  ^|  SysBroom v3.0 -- Suite de Limpieza Inteligente                     ^|
echo  +======================================================================+
echo  ^|  ESCANEO Y LIMPIEZA                                                  ^|
echo  ^|   sb              Asistente interactivo por fases                    ^|
echo  ^|   sb scan  [s]    Diagnostico completo (Windows+IA+Apps+Proc)        ^|
echo  ^|   sb clean [c]    Limpieza automatica segun perfil                   ^|
echo  ^|   sb dry   [sim]  Simular sin borrar nada (dry-run)                  ^|
echo  +----------------------------------------------------------------------+
echo  ^|  MODULOS DEDICADOS                                                   ^|
echo  ^|   sb ai    [a]    IA: Claude, Cursor, Ollama, HuggingFace, AGY...    ^|
echo  ^|   sb apps  [ap]   Apps: residuos, extensiones, venvs, node_modules   ^|
echo  ^|   sb docker[d]    Docker: imagenes, contenedores, volumenes, redes   ^|
echo  ^|   sb wsl   [w]    WSL: por distro y componente, compactacion VHDX    ^|
echo  ^|   sb proc  [p]    Procesos: zombies, CPU, RAM, puertos               ^|
echo  +----------------------------------------------------------------------+
echo  ^|  PROGRAMACION AUTOMATICA                                             ^|
echo  ^|   sb sched  [sch] Configurar dia, hora y categorias                  ^|
echo  ^|   sb status [st]  Estado y proxima ejecucion                         ^|
echo  ^|   sb unsched[un]  Eliminar tarea de Windows                          ^|
echo  +----------------------------------------------------------------------+
echo  ^|  HISTORIAL Y REPORTES                                                ^|
echo  ^|   sb history[hi]  Ultimas 10 limpiezas                               ^|
echo  ^|   sb report [r]   Ver el ultimo reporte                              ^|
echo  ^|   sb aliases[al]  Ver tabla de alias cortos                          ^|
echo  ^|   sb help   [h]   Este menu                                          ^|
echo  +======================================================================+
echo  ^|  TIP: Ctrl+C detiene cualquier proceso en ejecucion                  ^|
echo  +======================================================================+
echo.
GOTO :END

:ALIASES
echo.
echo  +==========================+===========+================================+
echo  ^|  Alias corto             ^|  Comando  ^|  Descripcion                   ^|
echo  +==========================+===========+================================+
echo  ^|  sb s                    ^|  sb scan  ^|  Diagnostico completo           ^|
echo  ^|  sb c                    ^|  sb clean ^|  Limpieza automatica            ^|
echo  ^|  sb sim / dry            ^|  sb dry   ^|  Simulacion (dry-run)           ^|
echo  ^|  sb a / ia               ^|  sb ai    ^|  Solo herramientas de IA        ^|
echo  ^|  sb ap / app             ^|  sb apps  ^|  Solo apps y residuos           ^|
echo  ^|  sb d / dk               ^|  sb docker^|  Solo Docker                    ^|
echo  ^|  sb w                    ^|  sb wsl   ^|  Solo WSL                       ^|
echo  ^|  sb p / ports            ^|  sb proc  ^|  Solo procesos y puertos        ^|
echo  ^|  sb sch                  ^|  sb sched ^|  Configurar programacion        ^|
echo  ^|  sb st                   ^|  sb status^|  Estado del scheduler           ^|
echo  ^|  sb un                   ^|  sb unsched^| Eliminar tarea programada     ^|
echo  ^|  sb hi / log             ^|  sb history^| Ultimas 10 limpiezas          ^|
echo  ^|  sb r / last             ^|  sb report^|  Ver el ultimo reporte          ^|
echo  ^|  sb al                   ^|  sb aliases^| Ver tabla de alias cortos     ^|
echo  ^|  sb h / ?                ^|  sb help  ^|  Menu de ayuda                  ^|
echo  +==========================+===========+================================+
echo  ^|  TIP: Ctrl+C detiene cualquier proceso en ejecucion                  ^|
echo  +======================================================================+
echo.
GOTO :END

:END
ENDLOCAL