@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  TFNK™ Neural Agent Desktop — Windows startup script
REM ─────────────────────────────────────────────────────────────────────────────
setlocal enabledelayedexpansion

SET "SCRIPT_DIR=%~dp0"
SET "PROJECT_ROOT=%SCRIPT_DIR%.."

REM ─── ASCII banner ─────────────────────────────────────────────────────────────
echo.
echo   TFNK(TM) Neural Agent Desktop
echo   =====================================
echo    ____  ____  ____  ____
echo   ^|_  _^|^|  __^|^|  _ \^|  _ \
echo     ^|^|  ^| ^|_   ^| ^| ^| ^| ^|_^| ^|
echo     ^|^|  ^|  _^|  ^| ^| ^| ^|  _ ^<
echo    _^|^|_ ^| ^|___ ^| ^|_^| ^| ^|_^| ^|
echo   ^|____^|^|____^|^|____/^|____/
echo.
echo   TFNK(TM) 神經代理桌面  -  自主 AI 代理工作站
echo   ─────────────────────────────────────────────
echo.

REM ─── Resolve project root (parent of scripts\) ────────────────────────────
PUSHD "%PROJECT_ROOT%"
SET "PROJECT_ROOT=%CD%"
POPD

echo   Project root : %PROJECT_ROOT%

REM ─── Activate virtual environment if present ──────────────────────────────
IF EXIST "%PROJECT_ROOT%\venv\Scripts\activate.bat" (
    echo   Activating   : %PROJECT_ROOT%\venv
    CALL "%PROJECT_ROOT%\venv\Scripts\activate.bat"
    GOTO :env_loaded
)
IF EXIST "%PROJECT_ROOT%\.venv\Scripts\activate.bat" (
    echo   Activating   : %PROJECT_ROOT%\.venv
    CALL "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
    GOTO :env_loaded
)

:env_loaded

REM ─── Move to project root ─────────────────────────────────────────────────
CD /D "%PROJECT_ROOT%"

REM ─── Load .env variables (simple key=value, no comments) ─────────────────
IF EXIST ".env" (
    FOR /F "usebackq tokens=1,* delims==" %%A IN (".env") DO (
        SET "LINE=%%A"
        IF NOT "!LINE:~0,1!"=="#" (
            IF NOT "%%A"=="" SET "%%A=%%B"
        )
    )
)

IF NOT DEFINED TFNK_HOST     SET "TFNK_HOST=0.0.0.0"
IF NOT DEFINED TFNK_PORT     SET "TFNK_PORT=8000"
IF NOT DEFINED TFNK_LOG_LEVEL SET "TFNK_LOG_LEVEL=info"

echo   Server       : http://%TFNK_HOST%:%TFNK_PORT%
echo   Log level    : %TFNK_LOG_LEVEL%
echo.
echo   Press Ctrl+C to stop.
echo.

REM ─── Determine Python executable ─────────────────────────────────────────
SET "PYTHON_EXE=python"
WHERE python >NUL 2>&1
IF ERRORLEVEL 1 (
    SET "PYTHON_EXE=py"
    WHERE py >NUL 2>&1
    IF ERRORLEVEL 1 (
        echo   ERROR: Python not found on PATH.
        echo   Install Python 3.11+ from https://www.python.org/downloads/
        PAUSE
        EXIT /B 1
    )
)

REM ─── Launch FastAPI ───────────────────────────────────────────────────────
%PYTHON_EXE% -m uvicorn webui.server:app ^
    --host %TFNK_HOST% ^
    --port %TFNK_PORT% ^
    --log-level %TFNK_LOG_LEVEL%

IF ERRORLEVEL 1 (
    echo.
    echo   Server exited with an error. Check the output above.
    PAUSE
)

endlocal
