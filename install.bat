@echo off
chcp 65001 > nul 2>&1
SETLOCAL

echo.
echo  +==================================================================+
echo  ^|          SysBroom v3.0 -- Instalacion de Dependencias           ^|
echo  +==================================================================+
echo  ^|  Este script instala todo lo necesario para usar SysBroom.      ^|
echo  ^|  Solo necesitas tener Python 3.9 o superior instalado.          ^|
echo  +==================================================================+
echo.

REM ── Verificar Python ─────────────────────────────────────────────────────────
python --version > nul 2>&1
IF ERRORLEVEL 1 (
    echo  [ERROR] Python no encontrado.
    echo.
    echo  Por favor instala Python desde: https://www.python.org/downloads/
    echo  Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

FOR /F "tokens=2" %%v IN ('python --version 2^>^&1') DO SET PYVER=%%v
echo  [OK] Python %PYVER% detectado.
echo.

REM ── Instalar dependencias ─────────────────────────────────────────────────────
echo  Instalando dependencias de SysBroom...
echo  (esto puede tardar unos segundos la primera vez)
echo.

python -m pip install --upgrade pip -q
python -m pip install -r "%~dp0requirements.txt" --quiet

IF ERRORLEVEL 1 (
    echo.
    echo  [ERROR] Hubo un problema instalando las dependencias.
    echo  Intenta ejecutar manualmente:
    echo      pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo  [OK] Todas las dependencias instaladas correctamente.
echo.

REM ── Verificar que funciona ────────────────────────────────────────────────────
python "%~dp0sysbroom.py" --version > nul 2>&1
IF ERRORLEVEL 1 (
    echo  [AVISO] Hubo un problema al verificar SysBroom.
    echo  Contacta al desarrollador o revisa los errores anteriores.
) ELSE (
    echo  [OK] SysBroom esta listo para usar.
)

echo.
echo  +==================================================================+
echo  ^|  LISTO. Usa los siguientes comandos desde esta carpeta:         ^|
echo  ^|                                                                  ^|
echo  ^|    sb              Asistente interactivo principal               ^|
echo  ^|    sb scan         Diagnostico completo del sistema              ^|
echo  ^|    sb ai           Auditar herramientas de IA                    ^|
echo  ^|    sb apps         Auditar apps y residuos                       ^|
echo  ^|    sb docker       Auditar Docker                                ^|
echo  ^|    sb help         Ver todos los comandos disponibles            ^|
echo  ^|                                                                  ^|
echo  ^|  TIP: ejecuta como Administrador para mejores resultados.        ^|
echo  +==================================================================+
echo.

pause
ENDLOCAL
