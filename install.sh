#!/usr/bin/env bash
# Dokima Installer — one-command setup
# Usage: curl -sSL https://get.dokima.dev | bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

err() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
log() { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

# ── Config (override via env) ────────────────────────────────────────
PANEL_REPO="${PANEL_REPO:-https://github.com/siongsheng/dokima.git}"
PANEL_DIR="${PANEL_DIR:-$HOME/.local/share/dokima}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"

# ── Parse Flags ──────────────────────────────────────────────────────
WITH_PROFILES=false
for arg in "$@"; do
    case "$arg" in
        --with-profiles) WITH_PROFILES=true ;;
    esac
done

# ── 1. Dependency Checks ────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || err "Python 3.6+ required but not found. Install Python: https://python.org"
command -v gh      >/dev/null 2>&1 || err "GitHub CLI (gh) required but not found. Install: https://cli.github.com"
command -v hermes  >/dev/null 2>&1 || err "Hermes Agent required but not found. Install: https://hermes-agent.nousresearch.com"

log "All prerequisites found: python3, gh, hermes"

# ── 2. Clone / Update Repo ──────────────────────────────────────────
if [ -d "$PANEL_DIR/.git" ]; then
    log "Repository exists — pulling latest"
    git -C "$PANEL_DIR" pull --ff-only 2>/dev/null || warn "Could not pull (dirty tree? skipping)"
else
    log "Cloning dokima to $PANEL_DIR"
    mkdir -p "$(dirname "$PANEL_DIR")"
    git clone "$PANEL_REPO" "$PANEL_DIR"
fi

# ── 3. Symlink dokima ───────────────────────────────────────────────
mkdir -p "$BIN_DIR"
if [ -L "$BIN_DIR/dokima" ] || [ -f "$BIN_DIR/dokima" ]; then
    log "dokima already linked in $BIN_DIR"
else
    ln -sf "$PANEL_DIR/dokima" "$BIN_DIR/dokima"
    log "Linked dokima → $BIN_DIR/dokima"
fi

# ── 4. Symlink nm and vet ────────────────────────────────────────────
for script in nm vet; do
    src="$PANEL_DIR/bin/$script"
    dest="$BIN_DIR/$script"
    if [ -f "$src" ]; then
        bash -n "$src" 2>/dev/null || warn "$script has syntax errors — symlinking anyway"
        if [ -L "$dest" ] || [ -f "$dest" ]; then
            log "$script already linked in $BIN_DIR"
        else
            ln -sf "$src" "$dest"
            log "Linked $script → $dest"
        fi
    else
        warn "$script not found in repo — skipping"
    fi
done

# ── 5. Initialize Profiles (--with-profiles) ──────────────────────────
if $WITH_PROFILES; then
    log "Initializing agent profiles..."
    for profile in strategist coder tech-lead nm; do
        if hermes profile list 2>/dev/null | grep -qw "$profile"; then
            log "Profile '$profile' already exists"
        else
            hermes profile create "$profile" 2>/dev/null || warn "Failed to create profile '$profile'"
            log "Profile '$profile' created"
        fi
    done
fi

# ── 6. PATH Detection ────────────────────────────────────────────────
case ":$PATH:" in
    *:"$BIN_DIR":*) ;;
    *)
        # Detect shell config file
        SHELL_RC=""
        case "$(basename "${SHELL:-/bin/bash}")" in
            zsh) SHELL_RC="$HOME/.zshrc" ;;
            *)   SHELL_RC="$HOME/.bashrc" ;;
        esac

        # Check if already in the config file (idempotency)
        if [ -f "$SHELL_RC" ] && grep -q "# dokima installer" "$SHELL_RC" 2>/dev/null; then
            log "PATH entry already in $SHELL_RC"
        else
            echo "" >> "$SHELL_RC"
            echo "# dokima installer — add ~/.local/bin to PATH" >> "$SHELL_RC"
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
            log "Added PATH entry to $SHELL_RC"
        fi

        echo ""
        echo "  To activate now, run: source $SHELL_RC"
        ;;
esac

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "  Dokima installed: $BIN_DIR/dokima"
if [ -f "$PANEL_DIR/bin/nm" ]; then
    echo "  nm installed:     $BIN_DIR/nm"
fi
if [ -f "$PANEL_DIR/bin/vet" ]; then
    echo "  vet installed:    $BIN_DIR/vet"
fi
echo ""
echo "  Next steps:"
echo "    dokima --help"
echo "    See docs/setup.md for full configuration"
