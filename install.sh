#!/usr/bin/env bash
# auditerm installer
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/auditerm/main/install.sh)

set -e

REPO="https://github.com/YOUR_USERNAME/auditerm"
CLONE_DIR="/tmp/auditerm_install"
VENV_DIR="$HOME/.local/share/auditerm/venv"
BIN_DIR="$HOME/.local/bin"

RED='\033[0;31m'
GRN='\033[0;32m'
CYN='\033[0;36m'
RST='\033[0m'

info()  { echo -e "${CYN}[auditerm]${RST} $*"; }
ok()    { echo -e "${GRN}[ok]${RST} $*"; }
error() { echo -e "${RED}[error]${RST} $*" >&2; exit 1; }

# ── check python ────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || error "python3 is required but not installed."
PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Found Python $PY"

# ── check pip ───────────────────────────────────────────────────
command -v pip3 >/dev/null 2>&1 || error "pip3 is required. Install python-pip from your package manager."

# ── clone repo ──────────────────────────────────────────────────
info "Cloning auditerm..."
rm -rf "$CLONE_DIR"
git clone --depth=1 "$REPO" "$CLONE_DIR" || error "Failed to clone repository."

# ── create venv ─────────────────────────────────────────────────
info "Creating virtual environment at $VENV_DIR..."
mkdir -p "$VENV_DIR"
python3 -m venv "$VENV_DIR"

info "Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install pygame mutagen numpy --quiet

# ── install auditerm into venv ──────────────────────────────────
info "Installing auditerm..."
cd "$CLONE_DIR"
"$VENV_DIR/bin/pip" install . --quiet

# ── wrapper script in ~/.local/bin ──────────────────────────────
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/auditerm" << EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/auditerm" "\$@"
EOF
chmod +x "$BIN_DIR/auditerm"

# ── PATH check ──────────────────────────────────────────────────
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    info "Adding $BIN_DIR to PATH..."
    SHELL_RC=""
    if [[ -f "$HOME/.bashrc" ]];  then SHELL_RC="$HOME/.bashrc"; fi
    if [[ -f "$HOME/.zshrc" ]];   then SHELL_RC="$HOME/.zshrc";  fi
    if [[ -n "$SHELL_RC" ]]; then
        echo "" >> "$SHELL_RC"
        echo "# auditerm" >> "$SHELL_RC"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
        ok "Added to $SHELL_RC — restart your terminal or run: source $SHELL_RC"
    else
        info "Add $BIN_DIR to your PATH manually."
    fi
fi

# ── cleanup ─────────────────────────────────────────────────────
rm -rf "$CLONE_DIR"

ok "auditerm installed! Run: auditerm"
