#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/haxpenguin2/auditerm"
CLONE_DIR="/tmp/auditerm_install"
VENV_DIR="$HOME/.local/share/auditerm/venv"
BIN_DIR="$HOME/.local/bin"

RED='\033[0;31m'
GRN='\033[0;32m'
CYN='\033[0;36m'
YLW='\033[0;33m'
RST='\033[0m'

info()  { echo -e "${CYN}◆ ${RST}$*"; }
ok()    { echo -e "${GRN}✔ ${RST}$*"; }
warn()  { echo -e "${YLW}⚠ ${RST}$*"; }

cleanup_old() {
    info "Removing previous auditerm install..."
    rm -rf "$CLONE_DIR" || true
    rm -rf "$VENV_DIR" || true
    rm -f "$HOME/.local/bin/auditerm" || true
    ok "Previous auditerm install removed"
}

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       auditerm  installer            ║"
echo "╚══════════════════════════════════════╝"
echo ""

# deps
info "Checking system dependencies..."
command -v python3 >/dev/null || { echo "python3 missing"; exit 1; }
command -v git >/dev/null || { echo "git missing"; exit 1; }

cleanup_old

# clone
info "Cloning auditerm..."
rm -rf "$CLONE_DIR"
git clone --depth=1 "$REPO" "$CLONE_DIR"
ok "Repository cloned"

# venv
info "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
ok "Virtual environment ready"

# pip bootstrap (THIS WAS YOUR BUG)
info "Bootstrapping build tools..."
"$VENV_DIR/bin/python" -m pip install -U pip setuptools wheel build

# runtime deps
info "Installing runtime dependencies..."
"$VENV_DIR/bin/pip" install mutagen numpy pygame-ce

# install project (verbose now so failures are visible)
info "Installing auditerm..."
cd "$CLONE_DIR"
"$VENV_DIR/bin/pip" install . --no-build-isolation --verbose

ok "auditerm installed"

# launcher
info "Creating launcher..."
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/auditerm" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/auditerm" "\$@"
EOF

chmod +x "$BIN_DIR/auditerm"
ok "Launcher created"

# PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR not in PATH (add export PATH=\"\$HOME/.local/bin:\$PATH\")"
fi

echo ""
echo "✔ installation complete"
echo "run: auditerm"
echo ""
