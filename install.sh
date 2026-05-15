\#!/usr/bin/env bash
# auditerm installer
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/haxpenguin2/auditerm/main/install.sh)

set -euo pipefail

REPO="https://github.com/haxpenguin2/auditerm"
CLONE_DIR="$(mktemp -d /tmp/auditerm_install.XXXXXX)"
BASE_DIR="$HOME/.local/share/auditerm"
VENV_DIR="$BASE_DIR/venv"
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

cleanup() {
    rm -rf "$CLONE_DIR" 2>/dev/null || true
    tput cnorm 2>/dev/null || true
}
trap cleanup EXIT

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
    printf "\r%-80s\r" " "
    tput cnorm 2>/dev/null || true
}

run_with_spinner() {
    local msg="$1"
    shift
    ( "$@" ) &
    local pid=$!
    spinner "$pid" "$msg"
    wait "$pid"
}

detect_pkg_manager() {
    if command -v pacman >/dev/null 2>&1; then
        echo "pacman"
    elif command -v apt-get >/dev/null 2>&1; then
        echo "apt"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    elif command -v zypper >/dev/null 2>&1; then
        echo "zypper"
    elif command -v apk >/dev/null 2>&1; then
        echo "apk"
    else
        echo "unknown"
    fi
}

install_system_pygame() {
    case "$(detect_pkg_manager)" in
        pacman)
            command -v sudo >/dev/null 2>&1 || error "sudo is required to install python-pygame from pacman."
            sudo pacman -S --needed --noconfirm python-pygame
            ;;
        apt)
            command -v sudo >/dev/null 2>&1 || error "sudo is required to install python3-pygame from apt."
            sudo apt-get update
            sudo apt-get install -y python3-pygame
            ;;
        dnf)
            command -v sudo >/dev/null 2>&1 || error "sudo is required to install python3-pygame from dnf."
            sudo dnf install -y python3-pygame
            ;;
        zypper)
            command -v sudo >/dev/null 2>&1 || error "sudo is required to install python3-pygame from zypper."
            sudo zypper --non-interactive install python3-pygame
            ;;
        apk)
            command -v sudo >/dev/null 2>&1 || error "sudo is required to install py3-pygame from apk."
            sudo apk add py3-pygame
            ;;
        *)
            return 1
            ;;
    esac
}

add_system_python_path_to_venv() {
    local system_site venv_site

    system_site="$(python3 - <<'PY'
import site
paths = site.getsitepackages()
print(paths[0] if paths else site.getusersitepackages())
PY
)"

    venv_site="$("$VENV_DIR/bin/python" - <<'PY'
import sysconfig
print(sysconfig.get_paths()["purelib"])
PY
)"

    mkdir -p "$venv_site"
    printf '%s\n' "$system_site" > "$venv_site/system-pygame.pth"
}

purge_previous_install() {
    info "Removing previous auditerm install..."
    rm -f "$BIN_DIR/auditerm"
    rm -rf "$BASE_DIR"
    ok "Previous auditerm install removed"
}

echo ""
echo -e "${CYN}╔══════════════════════════════════════╗${RST}"
echo -e "${CYN}║       auditerm  installer            ║${RST}"
echo -e "${CYN}╚══════════════════════════════════════╝${RST}"
echo ""

info "Checking system dependencies..."

command -v python3 >/dev/null 2>&1 || error "python3 is required. Install: sudo pacman -S python"
command -v git >/dev/null 2>&1 || error "git is required. Install: sudo pacman -S git"
command -v curl >/dev/null 2>&1 || error "curl is required. Install: sudo pacman -S curl"

python3 -m venv --help >/dev/null 2>&1 || error "python venv module missing. Install: sudo pacman -S python"

PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY found"

purge_previous_install

info "Cloning auditerm..."
run_with_spinner "Cloning repository..." git clone --depth=1 "$REPO" "$CLONE_DIR"
ok "Repository cloned"

info "Creating virtual environment..."
mkdir -p "$BASE_DIR"
python3 -m venv "$VENV_DIR"
ok "Virtual environment ready"

info "Upgrading pip tooling..."
run_with_spinner "Upgrading pip..." "$VENV_DIR/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
run_with_spinner "Installing pip/setuptools/wheel..." "$VENV_DIR/bin/pip" install -U pip setuptools wheel packaging -q
ok "pip ready"

info "Installing mutagen..."
run_with_spinner "Installing mutagen..." "$VENV_DIR/bin/pip" install mutagen -q
ok "mutagen installed"

info "Installing numpy..."
if run_with_spinner "Installing numpy..." "$VENV_DIR/bin/pip" install numpy --only-binary=:all: -q; then
    ok "numpy installed"
else
    error "Failed to install numpy (no prebuilt wheel for Python $PY). Try: sudo pacman -S python-numpy"
fi

info "Installing pygame..."
step "Trying prebuilt pygame-ce wheel first"

if run_with_spinner "Installing pygame-ce..." "$VENV_DIR/bin/pip" install pygame-ce --only-binary=:all: -q; then
    ok "pygame-ce installed"
else
    warn "No prebuilt pygame-ce wheel found for Python $PY. Falling back to system package manager..."
    if install_system_pygame; then
        add_system_python_path_to_venv
        ok "System pygame installed and linked into the venv"
    else
        error "Could not install pygame from package repositories."
    fi
fi

info "Verifying dependencies..."
"$VENV_DIR/bin/python" -c "import pygame" 2>/dev/null || error "pygame failed to import."
"$VENV_DIR/bin/python" -c "import mutagen" 2>/dev/null || error "mutagen failed to import."
"$VENV_DIR/bin/python" -c "import numpy" 2>/dev/null || error "numpy failed to import."
"$VENV_DIR/bin/python" -c "import curses" 2>/dev/null || error "curses not available."
ok "All dependencies verified"

info "Installing auditerm..."
cd "$CLONE_DIR"

export PIP_NO_CACHE_DIR=1

if run_with_spinner "Installing auditerm..." "$VENV_DIR/bin/pip" install . --no-build-isolation --no-cache-dir -q; then
    ok "auditerm installed"
else
    warn "pip install failed, trying legacy setup.py install..."
    run_with_spinner "Installing auditerm via setup.py..." "$VENV_DIR/bin/python" setup.py install >/dev/null 2>&1
    ok "auditerm installed"
fi

info "Creating launcher..."
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/auditerm" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/auditerm" "\$@"
EOF
chmod +x "$BIN_DIR/auditerm"
ok "Launcher created at $BIN_DIR/auditerm"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH"

    SHELL_RC=""
    case "${SHELL:-}" in
        */zsh)  [[ -f "$HOME/.zshrc" ]]  && SHELL_RC="$HOME/.zshrc" ;;
        */bash) [[ -f "$HOME/.bashrc" ]] && SHELL_RC="$HOME/.bashrc" ;;
    esac

    if [[ -z "$SHELL_RC" ]]; then
        [[ -f "$HOME/.bashrc" ]] && SHELL_RC="$HOME/.bashrc"
        [[ -f "$HOME/.zshrc" ]]  && SHELL_RC="$HOME/.zshrc"
    fi

    if [[ -n "$SHELL_RC" ]]; then
        if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$SHELL_RC" 2>/dev/null; then
            echo "" >> "$SHELL_RC"
            echo "# auditerm" >> "$SHELL_RC"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
        fi
        ok "Added to PATH in $SHELL_RC"
        warn "Apply now with: source $SHELL_RC"
    else
        warn 'Add this to your shell config: export PATH="$HOME/.local/bin:$PATH"'
    fi
else
    ok "$BIN_DIR already in PATH"
fi

echo ""
echo -e "${GRN}╔══════════════════════════════════════╗${RST}"
echo -e "${GRN}║      installation complete!          ║${RST}"
echo -e "${GRN}╚══════════════════════════════════════╝${RST}"
echo ""
echo -e "  Run ${CYN}auditerm${RST} to launch"
echo -e "  Config: ${DIM}~/.config/auditerm/config${RST}"
echo ""
