@echo off
REM ============================================================================
REM Heroes of Python -- Windows 10/11 Installer (install_windows.bat)
REM ============================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo   Heroes of Python -- Windows 10/11 Setup
echo ============================================================

REM 1. Check for Python 3; auto-install via winget if missing
echo [1/4] Checking for Python 3...
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo    Python not found on PATH. Installing Python 3.12 via winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%ProgramFiles%\Python312;%ProgramFiles%\Python312\Scripts;%PATH%"
)

REM Optional: Install Thonny IDE if not present
if not exist "%LocalAppData%\Programs\Thonny\thonny.exe" (
    echo    Installing Thonny IDE via winget...
    winget install -e --id AivarAnnamaa.Thonny --accept-package-agreements --accept-source-agreements
)

REM 2. Create .venv virtual environment
echo [2/4] Creating Python virtual environment (.venv)...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)

REM 3. Upgrade pip and install pygame + numpy
echo [3/4] Installing pygame and numpy into .venv...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip wheel setuptools
python -m pip install --upgrade pygame numpy

REM 4. Create play_windows.bat launcher & Desktop shortcut
echo [4/4] Creating play_windows.bat and Desktop shortcut...
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo start "" "%%~dp0.venv\Scripts\pythonw.exe" "%%~dp0run_game.py"
) > play_windows.bat

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Heroes of Python.lnk');$s.TargetPath='%~dp0.venv\Scripts\pythonw.exe';$s.Arguments='\"%~dp0run_game.py\"';$s.WorkingDirectory='%~dp0';$s.Save()"

echo.
echo Setup Complete! Double-click "Heroes of Python" on your Desktop to play!
pause