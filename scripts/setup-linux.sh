#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────────
# Hermes Panel — Linux Server Setup
# One-time machine setup. Idempotent — safe to re-run.
# Usage: chmod +x setup-linux.sh && ./setup-linux.sh
# ───────────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
section() { echo -e "\n${YELLOW}───${NC} $* ${YELLOW}───${NC}"; }

# ── Config (override via env) ──────────────────────────────────────
PANEL_REPO="${PANEL_REPO:-https://github.com/siongsheng/hermes-panel.git}"
PANEL_DIR="${PANEL_DIR:-$HOME/hermes-panel}"
BIN_DIR="${BIN_DIR:-$HOME/bin}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

# ── 1. Prerequisites Check ─────────────────────────────────────────
section "Checking prerequisites"

command -v hermes  >/dev/null 2>&1 || err "hermes CLI not found. Install Hermes Agent first."
command -v python3 >/dev/null 2>&1 || err "python3 not found. Install Python 3.6+."
command -v gh      >/dev/null 2>&1 || err "gh CLI not found. Install: https://cli.github.com"
command -v git     >/dev/null 2>&1 || err "git not found."

log "hermes:  $(hermes --version 2>&1 | head -1 || echo 'ok')"
log "python3: $(python3 --version)"
log "gh:      $(gh --version 2>&1 | head -1 || echo 'ok')"
log "git:     $(git --version)"

# adr-tools is optional
if command -v adr >/dev/null 2>&1; then
    log "adr-tools: $(adr version 2>&1 || echo 'ok')"
else
    warn "adr-tools not found — ADR lifecycle disabled. Install: https://github.com/npryce/adr-tools"
fi

# ── 2. Install the Panel ───────────────────────────────────────────
section "Installing hermes-panel"

if [ -d "$PANEL_DIR" ]; then
    log "Panel repo exists — pulling latest"
    git -C "$PANEL_DIR" pull --ff-only 2>/dev/null || warn "Could not pull (dirty tree? skipping)"
else
    log "Cloning hermes-panel to $PANEL_DIR"
    git clone "$PANEL_REPO" "$PANEL_DIR"
fi

# Symlink to ~/bin
mkdir -p "$BIN_DIR"
if [ -L "$BIN_DIR/hermes-panel" ] || [ -f "$BIN_DIR/hermes-panel" ]; then
    log "hermes-panel already linked in $BIN_DIR"
else
    ln -sf "$PANEL_DIR/hermes-panel" "$BIN_DIR/hermes-panel"
    log "Linked hermes-panel → $BIN_DIR/hermes-panel"
fi

# Ensure ~/bin is in PATH for this session
case ":$PATH:" in
    *:"$BIN_DIR":*) ;;
    *) export PATH="$BIN_DIR:$PATH" ;;
esac

# ── 3. Create Agent Profiles ───────────────────────────────────────
section "Creating agent profiles"

create_profile() {
    local name=$1
    local model=$2

    if hermes profile list 2>/dev/null | grep -qw "$name"; then
        log "Profile '$name' already exists"
    else
        log "Creating profile: $name"
        hermes profile create "$name"
    fi

    # Override specific config values (profile create gives full defaults)
    hermes --profile "$name" config set model.default "$model"
    hermes --profile "$name" config set model.provider deepseek
    hermes --profile "$name" config set agent.max_turns 150
    hermes --profile "$name" config set terminal.env_passthrough '[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]'

    if [ "$name" = "strategist" ]; then
        hermes --profile "$name" config set agent.reasoning_effort medium
    fi

    log "Profile '$name' configured ($model)"
}

create_profile "strategist" "deepseek-v4-pro"
create_profile "coder"      "deepseek-v4-flash"
create_profile "tech-lead"  "deepseek-v4-pro"

# ── 4. Deploy Panel Skills ────────────────────────────────────────
section "Deploying panel skills"

deploy_skill() {
    local src="$PANEL_DIR/skills/$1"
    local dest="$2/$1"

    if [ ! -d "$src" ]; then
        warn "Skill '$1' not found in repo — skipping (may have been removed)"
        return 0
    fi

    if [ -d "$dest" ]; then
        log "Skill exists: $dest"
    else
        mkdir -p "$(dirname "$dest")"
        cp -r "$src" "$dest"
        log "Deployed: $dest"
    fi
}

# Strategist skills
SKILLS_DIR="software-development"
STRAT_DIR="$HERMES_HOME/profiles/strategist/skills/$SKILLS_DIR"
COD_DIR="$HERMES_HOME/profiles/coder/skills/$SKILLS_DIR"
TL_DIR="$HERMES_HOME/profiles/tech-lead/skills/$SKILLS_DIR"
GLOB_DIR="$HERMES_HOME/skills/$SKILLS_DIR"

deploy_skill "spec-strategist-lite"          "$STRAT_DIR"
deploy_skill "ponytail-guard"                "$STRAT_DIR"
deploy_skill "ai-coding-best-practices-lite" "$COD_DIR"
deploy_skill "adversarial-review-lite"        "$TL_DIR"
deploy_skill "ponytail-guard"                "$TL_DIR"
deploy_skill "no-mistakes"                   "$GLOB_DIR"

# ── 5. GitHub Token ────────────────────────────────────────────────
section "GitHub token"

SHARED_ENV="$HERMES_HOME/shared.env"
if [ -f "$SHARED_ENV" ] && grep -q 'GH_TOKEN=' "$SHARED_ENV" 2>/dev/null; then
    log "GH_TOKEN already set in shared.env"
elif [ -t 0 ]; then
    # Interactive terminal — prompt for token
    warn "GH_TOKEN not found in $SHARED_ENV"
    echo ""
    echo "  Paste your GitHub token (needs 'repo' scope):"
    read -rsp "  GH_TOKEN: " GH_TOKEN_VALUE
    echo ""
    mkdir -p "$(dirname "$SHARED_ENV")"
    echo "GH_TOKEN=$GH_TOKEN_VALUE" >> "$SHARED_ENV"
    echo "GITHUB_TOKEN=$GH_TOKEN_VALUE" >> "$SHARED_ENV"
    log "Tokens written to $SHARED_ENV"
else
    warn "GH_TOKEN not set and no interactive terminal. Add manually:"
    echo "  echo 'GH_TOKEN=ghp_...' >> $SHARED_ENV"
    echo "  echo 'GITHUB_TOKEN=ghp_...' >> $SHARED_ENV"
fi

# ── 6. Verify ──────────────────────────────────────────────────────
section "Verifying setup"

# Check panel is executable
if python3 -c "compile(open('$PANEL_DIR/hermes-panel').read(), 'hermes-panel', 'exec')" 2>/dev/null; then
    log "hermes-panel: syntax OK"
else
    err "hermes-panel has syntax errors"
fi

# Quick profile smoke tests (non-blocking — warn only)
for profile in strategist coder tech-lead; do
    if hermes --profile "$profile" -q "echo ok" --yolo 2>/dev/null; then
        log "Profile '$profile': responds OK"
    else
        warn "Profile '$profile': smoke test failed (check API key / provider config)"
    fi
done

# ── Done ───────────────────────────────────────────────────────────
section "Setup complete"
echo ""
echo "  Next steps:"
echo "  1. Add AGENTS.md to your project root (see docs/setup.md §3.1)"
echo "  2. Run a smoke test:"
echo "     cd ~/your-project"
echo "     hermes-panel \"Add a comment\" ."
echo "  3. Force full pipeline test:"
echo "     PANEL_FORCE_FULL=1 hermes-panel \"Add a health check\" ."
echo ""
log "Happy orchestrating! 🎭"
