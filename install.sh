#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/haxpenguin2/auditerm"
CLONE_DIR="/tmp/auditerm_install"
VENV_DIR="$HOME/.local/share/auditerm/venv"
BIN_DIR="$HOME/.local/bin"
INSTALL_ROOT="$HOME/.local/share/auditerm"

CYN='\033[0;36m'
GRN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
RST='\033[0m'

info() { echo -e "${CYN}◆${RST} $*"; }
ok()   { echo -e "${GRN}✔${RST} $*"; }
err()  { echo -e "${RED}✘${RST} $*" >&2; exit 1; }

cleanup() {
    rm -rf "$CLONE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

echo ""
echo -e "${CYN}╔════════════════════════════╗${RST}"
echo -e "${CYN}║       auditerm setup       ║${RST}"
echo -e "${CYN}╚════════════════════════════╝${RST}"
echo ""

# ── deps ─────────────────────────────
info "Checking dependencies..."
command -v python3 >/dev/null || err "python3 missing"
command -v git >/dev/null || err "git missing"

# ── FULL WIPE ────────────────────────
info "Removing previous install (if any)..."
rm -rf "$INSTALL_ROOT"
rm -rf "$CLONE_DIR"
rm -rf "$BIN_DIR/auditerm"
ok "Clean slate ready"

# ── clone ────────────────────────────
info "Cloning repo..."
git clone --depth=1 "$REPO" "$CLONE_DIR" >/dev/null
ok "Repo cloned"

# ── venv ─────────────────────────────
info "Creating venv..."
rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR"
ok "venv created"

# ── pip core fix (IMPORTANT) ─────────
info "Upgrading pip tooling..."
"$VENV_DIR/bin/python" -m ensurepip --upgrade >/dev/null || true
"$VENV_DIR/bin/pip" install -U pip setuptools wheel >/dev/null
ok "pip + setuptools + wheel ready"

# ── system pygame fallback first ─────
info "Installing pygame from system (preferred)..."
if command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --needed --noconfirm python-pygame || true
elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y python3-pygame || true
fi

# try pip pygame-ce fallback
info "Trying pygame-ce..."
"$VENV_DIR/bin/pip" install pygame-ce --only-binary=:all: >/dev/null 2>&1 || true

# ── python deps ──────────────────────
info "Installing python deps..."
"$VENV_DIR/bin/pip" install mutagen numpy >/dev/null

# ── install package (FIXED MODE) ────
info "Installing auditerm..."

cd "$CLONE_DIR"

# THIS fixes your setuptools/build_meta crash
"$VENV_DIR/bin/pip" install . --no-build-isolation >/dev/null

ok "auditerm installed"

# ── launcher ─────────────────────────
info "Creating launcher..."
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/auditerm" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/auditerm" "\$@"
EOF

chmod +x "$BIN_DIR/auditerm"
ok "launcher ready"

echo ""
echo -e "${GRN}✔ install complete${RST}"
echo "run: auditerm"
