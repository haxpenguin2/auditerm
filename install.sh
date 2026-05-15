#!/usr/bin/env bash
set -e

REPO="https://github.com/haxpenguin2/auditerm"
INSTALL_DIR="$HOME/.local/share/auditerm-src"
VENV_DIR="$HOME/.local/share/auditerm/venv"
BIN="$HOME/.local/bin/auditerm"

echo "╔══════════════════════════════════════╗"
echo "║       auditerm  installer            ║"
echo "╚══════════════════════════════════════╝"

echo "◆ Removing previous install..."
rm -rf "$INSTALL_DIR"
rm -rf "$VENV_DIR"
rm -f "$BIN"
rm -rf "$HOME/.cache/pip"

echo "✔ Clean slate"

echo "◆ Cloning repo..."
git clone "$REPO" "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo "✔ cloned"

echo "◆ Creating venv..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "◆ Upgrading tooling..."
python -m pip install -U pip setuptools wheel --no-cache-dir

echo "◆ Installing runtime deps..."
python -m pip install mutagen numpy pygame-ce --no-cache-dir

echo "◆ DO NOT BUILD PACKAGE (avoiding pip wheel bug)"

# IMPORTANT: no pip install auditerm at all
# instead we just run from source

cat > "$BIN" << EOF
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$INSTALL_DIR"
python "$INSTALL_DIR/auditerm/main.py"
EOF

chmod +x "$BIN"

echo "✔ installed (source mode)"
echo ""
echo "run: auditerm"
