#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────────
# Dokima — Linux Server Setup
# One-time machine setup. Idempotent — safe to re-run.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/siongsheng/dokima/main/scripts/setup-linux.sh | bash
# ───────────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
section() { echo -e "\n${YELLOW}───${NC} $* ${YELLOW}───${NC}"; }
prompt() { echo -ne "${CYAN}→${NC} $* "; }

# Reconnect stdin to the real terminal if we're being piped (curl|bash).
# Falls back to non-interactive if no terminal is available (cron, no TTY).
if [ ! -t 0 ] && exec < /dev/tty 2>/dev/null; then
    INTERACTIVE=true
elif [ -t 0 ]; then
    INTERACTIVE=true
else
    INTERACTIVE=false
fi

# ── Config (override via env) ──────────────────────────────────────
PANEL_REPO="${PANEL_REPO:-https://github.com/siongsheng/dokima.git}"
PANEL_DIR="${PANEL_DIR:-$HOME/dokima}"
BIN_DIR="${BIN_DIR:-$HOME/bin}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SHARED_ENV="$HERMES_HOME/shared.env"

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

if command -v adr >/dev/null 2>&1; then
    log "adr-tools: $(adr version 2>&1 || echo 'ok')"
else
    warn "adr-tools not found — ADR lifecycle disabled. Install: https://github.com/npryce/adr-tools"
fi

# ── 2. Install the Panel ───────────────────────────────────────────
section "Installing dokima"

if [ -d "$PANEL_DIR" ]; then
    log "Panel repo exists — pulling latest"
    git -C "$PANEL_DIR" pull --ff-only 2>/dev/null || warn "Could not pull (dirty tree? skipping)"
else
    log "Cloning dokima to $PANEL_DIR"
    git clone "$PANEL_REPO" "$PANEL_DIR"
fi

mkdir -p "$BIN_DIR"
if [ -L "$BIN_DIR/dokima" ] || [ -f "$BIN_DIR/dokima" ]; then
    log "dokima already linked in $BIN_DIR"
else
    ln -sf "$PANEL_DIR/dokima" "$BIN_DIR/dokima"
    log "Linked dokima → $BIN_DIR/dokima"
fi

case ":$PATH:" in
    *:"$BIN_DIR":*) ;;
    *) export PATH="$BIN_DIR:$PATH" ;;
esac

# ── 3. Provider Configuration ──────────────────────────────────────
section "Provider Configuration"

# Provider catalog: provider_name → (api_key_env, strategist_model, coder_model, techlead_model)
declare -A PROVIDER_LABEL PROVIDER_KEY_ENV PROVIDER_S_MODEL PROVIDER_C_MODEL PROVIDER_T_MODEL

PROVIDER_LABEL[deepseek]="DeepSeek"
PROVIDER_KEY_ENV[deepseek]="DEEPSEEK_API_KEY"
PROVIDER_S_MODEL[deepseek]="deepseek-v4-pro"
PROVIDER_C_MODEL[deepseek]="deepseek-v4-flash"
PROVIDER_T_MODEL[deepseek]="deepseek-v4-pro"

PROVIDER_LABEL[anthropic]="Anthropic"
PROVIDER_KEY_ENV[anthropic]="ANTHROPIC_API_KEY"
PROVIDER_S_MODEL[anthropic]="claude-opus-4-20250514"
PROVIDER_C_MODEL[anthropic]="claude-sonnet-4-20250514"
PROVIDER_T_MODEL[anthropic]="claude-opus-4-20250514"

PROVIDER_LABEL[openai]="OpenAI"
PROVIDER_KEY_ENV[openai]="OPENAI_API_KEY"
PROVIDER_S_MODEL[openai]="gpt-5"
PROVIDER_C_MODEL[openai]="gpt-4o"
PROVIDER_T_MODEL[openai]="gpt-5"

PROVIDER_LABEL[openrouter]="OpenRouter (multi-provider)"
PROVIDER_KEY_ENV[openrouter]="OPENROUTER_API_KEY"
PROVIDER_S_MODEL[openrouter]="deepseek/deepseek-chat"
PROVIDER_C_MODEL[openrouter]="anthropic/claude-sonnet-4"
PROVIDER_T_MODEL[openrouter]="deepseek/deepseek-chat"

choose_provider() {
    local purpose="$1"
    local default="${2:-}"

    echo ""
    echo "  $purpose"
    echo "  ──────────────────────────────────────────"
    local i=1
    declare -A idx_to_key
    for key in deepseek anthropic openai openrouter; do
        echo "    $i) ${PROVIDER_LABEL[$key]}"
        idx_to_key[$i]=$key
        ((i++))
    done
    echo ""

    local choice
    while true; do
        prompt "Choose provider [1]:"
        read -r choice
        choice="${choice:-1}"
        if [[ "$choice" =~ ^[1-4]$ ]]; then
            echo "${idx_to_key[$choice]}"
            return
        fi
        warn "Enter 1-4"
    done
}

collect_api_key() {
    local provider=$1
    local key_env="${PROVIDER_KEY_ENV[$provider]}"

    # Already set?
    if [ -f "$SHARED_ENV" ] && grep -q "^${key_env}=" "$SHARED_ENV" 2>/dev/null; then
        log "${key_env} already set in shared.env"
        return 0
    fi

    # Check if it's in the environment already
    if [ -n "${!key_env:-}" ]; then
        log "${key_env} found in environment"
        return 0
    fi

    if ! $INTERACTIVE; then
        warn "No interactive terminal. Set ${key_env} in your environment:"
        echo "    export ${key_env}=your-key-here"
        return 0
    fi

    echo ""
    prompt "Paste your ${PROVIDER_LABEL[$provider]} API key:"
    read -rs API_KEY_VALUE
    echo ""

    if [ -z "$API_KEY_VALUE" ]; then
        warn "No key entered — profiles will need manual setup. Run: hermes --profile strategist setup"
        return 0
    fi

    mkdir -p "$(dirname "$SHARED_ENV")"
    echo "${key_env}=${API_KEY_VALUE}" >> "$SHARED_ENV"
    log "${key_env} saved to $SHARED_ENV"
}

# ── Choose primary provider
if $INTERACTIVE; then
    PRIMARY=$(choose_provider "Primary provider for all 3 roles (strategist, coder, tech-lead):")
else
    PRIMARY="deepseek"
    warn "Non-interactive mode — using DeepSeek as primary. Override with env vars."
fi

collect_api_key "$PRIMARY"

STRAT_MODEL="${PROVIDER_S_MODEL[$PRIMARY]}"
CODER_MODEL="${PROVIDER_C_MODEL[$PRIMARY]}"
TL_MODEL="${PROVIDER_T_MODEL[$PRIMARY]}"

echo ""
log "Primary: ${PROVIDER_LABEL[$PRIMARY]}"
echo "    strategist → $STRAT_MODEL"
echo "    coder      → $CODER_MODEL"
echo "    tech-lead  → $TL_MODEL"

# ── Optional secondary provider for nm
SECONDARY=""
if $INTERACTIVE; then
    echo ""
    echo "  Adversarial review (nm)"
    echo "  ──────────────────────────────────────────"
    echo "  nm catches model-family blind spots by using a DIFFERENT provider"
    echo "  from the coder. Skip this and nm reviews use the same provider"
    echo "  (weaker, but still catches code issues)."
    echo ""

    prompt "Add a secondary provider for nm? [y/N]:"
    read -r ADD_SECONDARY
    if [[ "$ADD_SECONDARY" =~ ^[Yy] ]]; then
        # Filter out the primary provider
        echo ""
        echo "  Available (excluding ${PROVIDER_LABEL[$PRIMARY]}):"
        local j=1
        declare -A sec_idx
        for key in deepseek anthropic openai openrouter; do
            if [ "$key" != "$PRIMARY" ]; then
                echo "    $j) ${PROVIDER_LABEL[$key]}"
                sec_idx[$j]=$key
                ((j++))
            fi
        done
        echo ""

        local sec_choice
        while true; do
            prompt "Choose nm provider [1]:"
            read -r sec_choice
            sec_choice="${sec_choice:-1}"
            if [ -n "${sec_idx[$sec_choice]:-}" ]; then
                SECONDARY="${sec_idx[$sec_choice]}"
                break
            fi
            warn "Enter 1-$((j-1))"
        done
        collect_api_key "$SECONDARY"
        log "nm provider: ${PROVIDER_LABEL[$SECONDARY]}"
    else
        warn "Skipping secondary provider — nm reviews will use ${PROVIDER_LABEL[$PRIMARY]}"
        echo "    (This weakens the adversarial review but the panel still works.)"
    fi
else
    warn "Non-interactive mode — skipping secondary provider. Set NM_PROVIDER env var to override."
fi

# ── 4. Create Agent Profiles ───────────────────────────────────────
section "Creating agent profiles"

create_profile() {
    local name=$1
    local model=$2
    local provider=$3

    if hermes profile list 2>/dev/null | grep -qw "$name"; then
        log "Profile '$name' already exists"
    else
        log "Creating profile: $name"
        hermes profile create "$name"
    fi

    hermes --profile "$name" config set model.default "$model"
    hermes --profile "$name" config set model.provider "$provider"
    hermes --profile "$name" config set agent.max_turns 150
    hermes --profile "$name" config set terminal.env_passthrough '[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]'

    if [ "$name" = "strategist" ]; then
        hermes --profile "$name" config set agent.reasoning_effort high
    fi

    log "Profile '$name' configured ($model @ $provider)"
}

create_profile "strategist" "$STRAT_MODEL" "$PRIMARY"
create_profile "coder"      "$CODER_MODEL" "$PRIMARY"
create_profile "tech-lead"  "$TL_MODEL"     "$PRIMARY"

# Configure nm profile if secondary provider chosen
if [ -n "$SECONDARY" ]; then
    NM_MODEL="${PROVIDER_S_MODEL[$SECONDARY]}"
    create_profile "nm" "$NM_MODEL" "$SECONDARY"
fi

# ── 5. Deploy Panel Skills ────────────────────────────────────────
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

SKILLS_DIR="software-development"
STRAT_DIR="$HERMES_HOME/profiles/strategist/skills/$SKILLS_DIR"
COD_DIR="$HERMES_HOME/profiles/coder/skills/$SKILLS_DIR"
TL_DIR="$HERMES_HOME/profiles/tech-lead/skills/$SKILLS_DIR"
GLOB_DIR="$HERMES_HOME/skills/$SKILLS_DIR"

deploy_skill "spec-strategist-lite"          "$STRAT_DIR"
deploy_skill "ponytail-guard"                "$STRAT_DIR"
deploy_skill "spec-kit"                      "$STRAT_DIR"
deploy_skill "saas-ideation"                 "$STRAT_DIR"
deploy_skill "ai-coding-best-practices-lite" "$COD_DIR"
deploy_skill "adversarial-review-lite"        "$TL_DIR"
deploy_skill "ponytail-guard"                "$TL_DIR"
deploy_skill "no-mistakes"                   "$GLOB_DIR"
deploy_skill "spec-kit"                      "$GLOB_DIR"
deploy_skill "saas-ideation"                 "$GLOB_DIR"

# ── 6. GitHub Token ────────────────────────────────────────────────
section "GitHub token"

if [ -f "$SHARED_ENV" ] && grep -q 'GH_TOKEN=' "$SHARED_ENV" 2>/dev/null; then
    log "GH_TOKEN already set in shared.env"
elif $INTERACTIVE; then
    warn "GH_TOKEN not found in $SHARED_ENV"
    echo ""
    echo "  Paste your GitHub token (needs 'repo' scope):"
    read -rs -p "  GH_TOKEN: " GH_TOKEN_VALUE
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

# ── 7. Verify ──────────────────────────────────────────────────────
section "Verifying setup"

if python3 -c "compile(open('$PANEL_DIR/dokima').read(), 'dokima', 'exec')" 2>/dev/null; then
    log "dokima: syntax OK"
else
    err "dokima has syntax errors"
fi

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
echo "  Profiles:"
echo "    strategist  → $STRAT_MODEL (${PROVIDER_LABEL[$PRIMARY]})"
echo "    coder       → $CODER_MODEL (${PROVIDER_LABEL[$PRIMARY]})"
echo "    tech-lead   → $TL_MODEL (${PROVIDER_LABEL[$PRIMARY]})"
if [ -n "$SECONDARY" ]; then
    echo "    nm          → $NM_MODEL (${PROVIDER_LABEL[$SECONDARY]})"
else
    echo "    nm          → same as coder (no secondary provider configured)"
fi
echo ""
echo "  Next steps:"
echo "  1. Add AGENTS.md to your project root (see docs/setup.md §3.1)"
echo "  2. Run a smoke test:"
echo "     cd ~/your-project"
echo "     dokima \"Add a comment\" ."
echo "  3. Force full pipeline test:"
echo "     PANEL_FORCE_FULL=1 dokima \"Add a health check\" ."
echo ""
log "Happy orchestrating! 🎭"
