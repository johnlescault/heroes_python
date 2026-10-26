# ============================================================================
# ⚔ HEROES OF PYTHON — Windows 10 / 11 Installer (install_windows.ps1)
# ============================================================================
# Checks for Python 3 (and installs Python 3.12 + Thonny via winget if missing),
# creates the `.venv` virtual environment, installs `pygame` and `numpy`,
# and creates a `play_windows.bat` launcher + Desktop shortcut!
# ============================================================================
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "⚔  Heroes of Python — Windows 10 / 11 Setup" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow

# 1. Check for Python 3; auto-install via winget if missing
Write-Host "`n[1/4] Checking for Python 3..." -ForegroundColor Cyan
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Host "   Python not found on PATH. Installing Python 3.12 via winget..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

python --version

# Optional: Install Thonny IDE if not present
if (-not (Test-Path "$env:LocalAppData\Programs\Thonny\thonny.exe")) {
    Write-Host "   Installing Thonny IDE for kids (via winget)..." -ForegroundColor Cyan
    winget install -e --id AivarAnnamaa.Thonny --accept-package-agreements --accept-source-agreements
}

# 2. Create the .venv virtual environment
Write-Host "`n[2/4] Creating Python virtual environment (.venv)..." -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
    Write-Host "   ✓ Created .venv" -ForegroundColor Green
} else {
    Write-Host "   ✓ Found existing .venv" -ForegroundColor Green
}

# 3. Upgrade pip and install pygame + numpy
Write-Host "`n[3/4] Installing Python packages (pygame, numpy) into .venv..." -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m pip install --upgrade pip wheel setuptools
& ".venv\Scripts\python.exe" -m pip install --upgrade pygame numpy
& ".venv\Scripts\python.exe" -c "import pygame, numpy; print(f'   ✓ Pygame {pygame.version.ver} + NumPy {numpy.__version__} ready!')"

# 4. Create play_windows.bat and Desktop Shortcut
Write-Host "`n[4/4] Creating play_windows.bat launcher and Desktop shortcut..." -ForegroundColor Cyan
$batContent = "@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" `"%~dp0.venv\Scripts\pythonw.exe`" `"%~dp0run_game.py`"`r`n"
Set-Content -Path "play_windows.bat" -Value $batContent -Encoding ASCII

$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut("$Desktop\Heroes of Python.lnk")
$Shortcut.TargetPath = "$PSScriptRoot\.venv\Scripts\pythonw.exe"
$Shortcut.Arguments = "`"$PSScriptRoot\run_game.py`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Heroes of Python - Self-Teaching Campaign"
$Shortcut.Save()

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "🎉 Setup Complete!" -ForegroundColor Green
Write-Host "   • Double-click 'Heroes of Python' on your Desktop (or play_windows.bat)!"
Write-Host "   • In Thonny: Tools -> Options -> Interpreter -> select:"
Write-Host "     $PSScriptRoot\.venv\Scripts\python.exe"
Write-Host "============================================================" -ForegroundColor Green
