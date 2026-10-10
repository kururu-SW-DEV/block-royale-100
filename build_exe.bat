@echo off
REM BLOCK ROYALE 100 - single-file exe build
REM Requires: pip install -r requirements.txt pyinstaller
cd /d "%~dp0"
if not exist assets\fonts mkdir assets\fonts
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name BlockRoyale100 --icon ..\icon.ico ^
  --add-data "..\icon.png;." ^
  --add-data "..\assets\fonts;assets\fonts" ^
  --exclude-module tkinter --exclude-module matplotlib --exclude-module PIL --exclude-module scipy ^
  --distpath release --workpath build_tmp --specpath build_tmp ^
  main.py
if %errorlevel% neq 0 (
    echo [ERROR] build failed
    pause
    exit /b 1
)
copy /y LICENSE release\ >nul
copy /y THIRD_PARTY_NOTICES.md release\ >nul
echo Build complete: release\BlockRoyale100.exe
