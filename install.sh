#!/usr/bin/env bash
# auditerm installer
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/haxpenguin2/auditerm/main/install.sh)

set -e

REPO="https://github.com/haxpenguin2/auditerm"
CLONE_DIR="/tmp/auditerm_install"
VENV_DIR="$HOME/.local/share/auditerm/venv"
BIN_DIR="$HOME/.local/bin"

RED='\033[0;31m'
GRN='\033[0;32m'
CYN='\033[0;36m'
YLW='\033[0;33m'
DIM='\033[2m'
RST='\033[0m'

info()  { echo -e "${CYN}◆ ${RST}$*"; }
ok()    { echo -e "${GRN}✔ ${RST}$*"; }
warn()  { echo -e "${YLW}⚠ ${RST}$*"; }
error() { echo -e "${RED}✘ ${RST}$*" >&2; exit 1; }
step()  { echo -e "${DIM}  → $*${RST}"; }

spinner() {
    local pid=$1
    local msg=$2
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    tput civis 2>/dev/null || true
    while kill -0 "$pid" 2>/dev/null; do
        local c="${spin:$((i % ${#spin})):1}"
        printf "\r  ${CYN}%s${RST}  %s " "$c" "$msg"
        sleep 0.1
        ((i++)) || true
    done
    printf "\r%-60s\r" " "
    tput cnorm 2>/dev/null || true
}

echo ""
echo -e "${CYN}╔══════════════════════════════════════╗${RST}"
echo -e "${CYN}║       auditerm  installer            ║${RST}"
echo -e "${CYN}╚══════════════════════════════════════╝${RST}"
echo ""

# ── check dependencies ──────────────────────────────────────────
info "Checking system dependencies..."

command -v python3 >/dev/null 2>&1 || error "python3 is required. Install: sudo pacman -S python"
command -v git     >/dev/null 2>&1 || error "git is required. Install: sudo pacman -S git"
command -v curl    >/dev/null 2>&1 || error "curl is required. Install: sudo pacman -S curl"

PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY found"

python3 -m venv --help >/dev/null 2>&1 || error "python venv module missing. Install: sudo pacman -S python"

# ── clone repo ──────────────────────────────────────────────────
info "Cloning auditerm..."
rm -rf "$CLONE_DIR"
(git clone --depth=1 "$REPO" "$CLONE_DIR" 2>&1) &
spinner $! "Cloning repository..."
wait $! || error "Failed to clone repository."
ok "Repository cloned"

# ── create venv ─────────────────────────────────────────────────
info "Creating virtual environment..."
mkdir -p "$(dirname "$VENV_DIR")"
rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR"
ok "Virtual environment ready"

# ── upgrade pip quietly ─────────────────────────────────────────
("$VENV_DIR/bin/pip" install --upgrade pip -q 2>&1) &
spinner $! "Upgrading pip..."
wait $! || true
ok "pip ready"

# ── install mutagen (pure python, fast) ─────────────────────────
info "Installing mutagen..."
(
    "$VENV_DIR/bin/pip" install mutagen -q 2>&1
) &
spinner $! "Installing mutagen..."
wait $! || error "Failed to install mutagen."
ok "mutagen installed"

# ── install numpy (prebuilt wheel) ──────────────────────────────
info "Installing numpy..."
(
    "$VENV_DIR/bin/pip" install "numpy" --only-binary=:all: -q 2>&1
) &
spinner $! "Installing numpy..."
wait $! || error "Failed to install numpy (no prebuilt wheel for Python $PY). Try: sudo pacman -S python-numpy"
ok "numpy installed"

# ── install pygame-ce (has wheels for Python 3.13+) ─────────────
info "Installing pygame-ce (prebuilt wheel, no compilation)..."
step "pygame-ce is a drop-in replacement for pygame with Python 3.13/3.14 support"
(
    "$VENV_DIR/bin/pip" install pygame-ce --only-binary=:all: -q 2>&1
) &
spinner $! "Installing pygame-ce..."
if ! wait $!; then
    warn "pygame-ce prebuilt wheel not found for Python $PY, falling back to system pygame..."
    if command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --noconfirm python-pygame || error "Could not install pygame. Try manually: sudo pacman -S python-pygame"
        PY_VER=$(python3 -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")
        SITE_PKGS="$VENV_DIR/lib/$PY_VER/site-packages"
        SYS_PYGAME=$(python3 -c "import pygame; import os; print(os.path.dirname(pygame.__file__))" 2>/dev/null || true)
        if [[ -n "$SYS_PYGAME" ]]; then
            ln -sfn "$SYS_PYGAME" "$SITE_PKGS/pygame"
            ok "Linked system pygame into venv"
        else
            error "Could not locate system pygame after install."
        fi
    else
        error "No prebuilt pygame wheel for Python $PY and pacman not found."
    fi
else
    ok "pygame-ce installed"
fi

# ── verify imports ──────────────────────────────────────────────
info "Verifying dependencies..."
"$VENV_DIR/bin/python" -c "import pygame" 2>/dev/null   || error "pygame failed to import."
"$VENV_DIR/bin/python" -c "import mutagen" 2>/dev/null  || error "mutagen failed to import."
"$VENV_DIR/bin/python" -c "import numpy" 2>/dev/null    || error "numpy failed to import."
"$VENV_DIR/bin/python" -c "import curses" 2>/dev/null   || error "curses not available."
ok "All dependencies verified"

# ── install auditerm ────────────────────────────────────────────
info "Installing auditerm..."
(
    cd "$CLONE_DIR"
    "$VENV_DIR/bin/pip" install . -q 2>&1
) &
spinner $! "Installing auditerm..."
wait $! || error "Failed to install auditerm."
ok "auditerm installed"

# ── wrapper script ──────────────────────────────────────────────
info "Creating launcher..."
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/auditerm" << EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/auditerm" "\$@"
EOF
chmod +x "$BIN_DIR/auditerm"
ok "Launcher created at $BIN_DIR/auditerm"

# ── PATH check ──────────────────────────────────────────────────
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH"
    SHELL_RC=""
    [[ -f "$HOME/.bashrc" ]] && SHELL_RC="$HOME/.bashrc"
    [[ -f "$HOME/.zshrc"  ]] && SHELL_RC="$HOME/.zshrc"
    if [[ -n "$SHELL_RC" ]]; then
        echo "" >> "$SHELL_RC"
        echo "# auditerm" >> "$SHELL_RC"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
        ok "Added to PATH in $SHELL_RC"
        warn "Apply now with: source $SHELL_RC"
    else
        warn "Add this to your shell config: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
else
    ok "$BIN_DIR already in PATH"
fi

# ── cleanup ─────────────────────────────────────────────────────
rm -rf "$CLONE_DIR"

echo ""
echo -e "${GRN}╔══════════════════════════════════════╗${RST}"
echo -e "${GRN}║      installation complete!          ║${RST}"
echo -e "${GRN}╚══════════════════════════════════════╝${RST}"
echo ""
echo -e "  Run ${CYN}auditerm${RST} to launch"
echo -e "  Config: ${DIM}~/.config/auditerm/config${RST}"
echo ""
