@echo off
cd /d "%~dp0"
title BLOCK ROYALE 100

echo ========================================================
echo        Starting BLOCK ROYALE 100 ...
echo ========================================================
echo.

set "PY_EXE="

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_EXE=python"
    goto :RUN
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_EXE=py -3"
    goto :RUN
)

echo [ERROR] Python 3.10+ could not be found! Please install Python and run:
echo         pip install -r requirements.txt
pause
exit /b 1

:RUN
echo Using Python: %PY_EXE%
echo Launching game...
%PY_EXE% main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The game exited with error code: %errorlevel%
    echo If modules are missing, run: pip install -r requirements.txt
    pause
)
