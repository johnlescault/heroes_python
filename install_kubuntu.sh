#!/usr/bin/env bash
# ============================================================================
# ⚔ HEROES OF PYTHON — Kubuntu / Ubuntu / Debian Installer (install_kubuntu.sh)
# ============================================================================
# Installs Python 3, venv, Tkinter (for clipboard), DejaVu fonts, SDL2 audio/
# graphics libraries, creates the `.venv` virtual environment, installs
# `pygame` and `numpy`, and generates a one-click launcher (`play.sh` +
# KDE Desktop shortcut).
# ============================================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "============================================================"
echo "⚔  Heroes of Python — Kubuntu / Linux Setup"
echo "============================================================"

# 1. Install system packages (Python 3, venv, Tkinter, DejaVu fonts, SDL2)
echo "📦 [1/4] Checking & installing system packages (requires sudo)..."
sudo apt-get update -y
sudo apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-tk \
    fonts-dejavu-core \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev

# Optional: Suggest Thonny IDE if not installed
if ! command -v thonny &> /dev/null; then
    echo "💡 Optional: Installing Thonny IDE (great for kids editing my_hero.py)..."
    sudo apt-get install -y thonny || true
fi

# 2. Create the .venv virtual environment
echo "🐍 [2/4] Creating Python virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "   Created .venv/"
else
    echo "   Found existing .venv/"
fi

# 3. Upgrade pip and install Python dependencies (pygame & numpy)
echo "⚡ [3/4] Installing Python packages (pygame, numpy) into .venv..."
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
python -m pip install --upgrade pygame numpy

# Verify installation
python -c "import pygame, numpy; print(f'   ✓ Pygame {pygame.version.ver} + NumPy {numpy.__version__} ready!')"

# 4. Create one-click play.sh launcher & KDE Desktop shortcut
echo "🚀 [4/4] Creating play.sh launcher and KDE Desktop shortcut..."
cat << 'LAUNCH_EOF' > "$PROJECT_DIR/play.sh"
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
exec "$DIR/.venv/bin/python" "$DIR/run_game.py" "$@"
LAUNCH_EOF
chmod +x "$PROJECT_DIR/play.sh"

DESKTOP_FILE="$HOME/Desktop/HeroesOfPython.desktop"
if [ -d "$HOME/Desktop" ]; then
    cat << DESK_EOF > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=Heroes of Python
Comment=Self-Teaching Python Campaign & Duel Edition
Exec="$PROJECT_DIR/play.sh"
Path=$PROJECT_DIR
Icon=$PROJECT_DIR/game_engine/assets/hero.png
Terminal=false
Categories=Game;Education;
DESK_EOF
    chmod +x "$DESKTOP_FILE"
    echo "   ✓ Created Desktop shortcut: $DESKTOP_FILE"
fi

echo ""
echo "============================================================"
echo "🎉 Setup Complete!"
echo "   • To play from terminal:  ./play.sh"
echo "   • Or double-click 'Heroes of Python' on your Desktop!"
echo "   • In Thonny: Tools -> Options -> Interpreter -> select:"
echo "     $PROJECT_DIR/.venv/bin/python"
echo "============================================================"
