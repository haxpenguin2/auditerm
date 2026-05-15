#!/usr/bin/env bash
set -e

REPO="https://github.com/haxpenguin2/auditerm"
INSTALL_TMP="/tmp/auditerm_install"
VENV_DIR="$HOME/.local/share/auditerm/venv"
BIN_DIR="$HOME/.local/bin"
SHARE_DIR="$HOME/.local/share/auditerm"

echo "╔══════════════════════════════════════╗"
echo "║       auditerm  installer            ║"
echo "╚══════════════════════════════════════╝"

echo "◆ Checking system dependencies..."

command -v python3 >/dev/null || { echo "Python3 not found"; exit 1; }
echo "✔ Python found"

echo "◆ Removing previous auditerm install..."

# kill old venv + install artifacts
rm -rf "$INSTALL_TMP" || true
rm -rf "$SHARE_DIR" || true
rm -rf "$HOME/.cache/pip" || true
rm -f "$BIN_DIR/auditerm" || true

# also purge any pip installs inside venv if it exists
python3 -m pip uninstall auditerm -y >/dev/null 2>&1 || true

echo "✔ Previous auditerm install removed"

echo "◆ Cloning auditerm..."
git clone "$REPO" "$INSTALL_TMP"
echo "✔ Repository cloned"

cd "$INSTALL_TMP"

echo "◆ Creating virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
echo "✔ Virtual environment ready"

echo "◆ Bootstrapping build tools..."
python -m pip install -U pip setuptools wheel build --no-cache-dir

echo "◆ Installing runtime dependencies..."
python -m pip install mutagen numpy pygame-ce --no-cache-dir

echo "◆ Installing auditerm (EDITABLE MODE)..."

# THIS is the important fix
# prevents stale wheel/site-packages conflicts
python -m pip install -e . --no-cache-dir

echo "✔ auditerm installed"

echo "◆ Creating launcher..."
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/auditerm" << EOF
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
python -m auditerm.main
EOF

chmod +x "$BIN_DIR/auditerm"

echo "✔ Launcher created at $BIN_DIR/auditerm"

echo "✔ Done!"
echo ""
echo "Run: auditerm"
