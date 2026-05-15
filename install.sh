#!/usr/bin/env bash
# auditerm installer
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/haxpenguin2/auditerm/main/install.sh)

set -e

REPO="https://github.com/haxpenguin2/auditerm"
INSTALL_DIR="$HOME/.local/share/auditerm-src"
VENV_DIR="$HOME/.local/share/auditerm/venv"
BIN="$HOME/.local/bin/auditerm"
BIN_DIR="$HOME/.local/bin"

RED='\033[0;31m'; GRN='\033[0;32m'; CYN='\033[0;36m'; DIM='\033[2m'; RST='\033[0m'
info() { echo -e "${CYN}◆ ${RST}$*"; }
ok()   { echo -e "${GRN}✔ ${RST}$*"; }
die()  { echo -e "${RED}✘ ${RST}$*" >&2; exit 1; }

spinner() {
    local pid=$1 msg=$2 spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0
    tput civis 2>/dev/null || true
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYN}%s${RST}  %s " "${spin:$((i%${#spin})):1}" "$msg"
        sleep 0.1; ((i++)) || true
    done
    printf "\r%-70s\r" " "
    tput cnorm 2>/dev/null || true
}

echo ""
echo -e "${CYN}╔══════════════════════════════════════╗${RST}"
echo -e "${CYN}║       auditerm  installer            ║${RST}"
echo -e "${CYN}╚══════════════════════════════════════╝${RST}"
echo ""

# ── requirements ────────────────────────────────────────────────
info "Checking requirements..."
command -v python3 >/dev/null 2>&1 || die "python3 not found. Install: sudo pacman -S python"
command -v git     >/dev/null 2>&1 || die "git not found.     Install: sudo pacman -S git"
PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY"

# ── clean previous install ──────────────────────────────────────
info "Removing previous install..."
pkill -f "auditerm" 2>/dev/null || true
rm -rf "$INSTALL_DIR" "$VENV_DIR" "$BIN"
ok "Clean slate"

# ── system packages (pygame, numpy — prebuilt, no compilation) ──
info "Installing system packages via pacman..."
NEEDED=()
python3 -c "import pygame" 2>/dev/null || NEEDED+=("python-pygame")
python3 -c "import numpy"  2>/dev/null || NEEDED+=("python-numpy")
if [[ ${#NEEDED[@]} -gt 0 ]]; then
    sudo pacman -S --noconfirm --needed "${NEEDED[@]}" \
        || die "pacman failed. Try: sudo pacman -S python-pygame python-numpy"
fi
python3 -c "import pygame" 2>/dev/null || die "pygame still not importable."
python3 -c "import numpy"  2>/dev/null || die "numpy still not importable."
ok "pygame + numpy ready (system packages)"

# ── clone ───────────────────────────────────────────────────────
info "Cloning auditerm..."
(git clone --depth=1 "$REPO" "$INSTALL_DIR" 2>&1) &
spinner $! "Fetching from GitHub..."
wait $! || die "Clone failed. Check your internet connection."
ok "Repository cloned"

# ── venv with system packages visible ───────────────────────────
info "Creating virtual environment..."
python3 -m venv --system-site-packages "$VENV_DIR"
ok "venv created at $VENV_DIR"

# ── pip: only pure-python packages needed (fast) ────────────────
info "Installing Python dependencies..."
(
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install mutagen -q
) &
spinner $! "Installing mutagen..."
wait $! || die "pip install failed."
ok "mutagen installed"

# ── install auditerm package into venv ──────────────────────────
info "Installing auditerm..."
(
    cd "$INSTALL_DIR"
    # Remove pygame-ce from install_requires so pip doesn't try to
    # download/compile it — we're using the system package instead
    sed -i 's/"pygame-ce",//' setup.py 2>/dev/null || true
    sed -i 's/"pygame",//'    setup.py 2>/dev/null || true
    "$VENV_DIR/bin/pip" install . -q
) &
spinner $! "Installing auditerm package..."
wait $! || die "auditerm install failed."
ok "auditerm installed"

# ── verify all imports ──────────────────────────────────────────
info "Verifying..."
"$VENV_DIR/bin/python" -c "import pygame, numpy, mutagen, curses" \
    || die "Import check failed. Check errors above."
ok "All imports verified"

# ── launcher script ─────────────────────────────────────────────
info "Creating launcher..."
mkdir -p "$BIN_DIR"
# Use the venv's auditerm entry point directly (installed by setup.py)
cat > "$BIN" << LAUNCHER
#!/usr/bin/env bash
exec "$VENV_DIR/bin/auditerm" "\$@"
LAUNCHER
chmod +x "$BIN"
ok "Launcher: $BIN"

# ── PATH ────────────────────────────────────────────────────────
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    RCFILE=""
    [[ -f "$HOME/.zshrc"  ]] && RCFILE="$HOME/.zshrc"
    [[ -f "$HOME/.bashrc" ]] && RCFILE="$HOME/.bashrc"
    if [[ -n "$RCFILE" ]]; then
        grep -q 'auditerm' "$RCFILE" 2>/dev/null || {
            printf '\n# auditerm\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$RCFILE"
        }
        ok "Added ~/.local/bin to PATH in $RCFILE"
        echo -e "  ${DIM}Apply now: source $RCFILE${RST}"
    else
        echo -e "  ${DIM}Add to your shell rc: export PATH=\"\$HOME/.local/bin:\$PATH\"${RST}"
    fi
else
    ok "~/.local/bin already in PATH"
fi

echo ""
echo -e "${GRN}╔══════════════════════════════════════╗${RST}"
echo -e "${GRN}║     installation complete!           ║${RST}"
echo -e "${GRN}╚══════════════════════════════════════╝${RST}"
echo ""
echo -e "  Run ${CYN}auditerm${RST} to launch"
echo -e "  Config: ${DIM}~/.config/auditerm/config${RST}"
echo ""
