# ───────────────────────────────────────────────────────────────────
# Hermes Panel — Windows PC Setup
# One-time machine setup. Idempotent — safe to re-run.
# Usage:
#   irm https://raw.githubusercontent.com/siongsheng/hermes-panel/main/scripts/setup-windows.ps1 | iex
# ───────────────────────────────────────────────────────────────────
param(
    [string]$PanelRepo = "https://github.com/siongsheng/hermes-panel.git",
    [string]$PanelDir  = "$env:USERPROFILE\hermes-panel",
    [string]$BinDir    = "$env:USERPROFILE\bin",
    [string]$HermesHome = "$env:USERPROFILE\.hermes"
)

$ErrorActionPreference = "Stop"

function Write-Step  { Write-Host "`n─── $args ───" -ForegroundColor Yellow }
function Write-OK    { Write-Host "[✓] $args"      -ForegroundColor Green }
function Write-Warn  { Write-Host "[!] $args"      -ForegroundColor Yellow }
function Write-Err   { Write-Host "[✗] $args"      -ForegroundColor Red; exit 1 }
function Write-Prompt { Write-Host -NoNewline "→ $args " -ForegroundColor Cyan }

$sharedEnv = "$HermesHome\shared.env"

# ── 1. Prerequisites Check ─────────────────────────────────────────
Write-Step "Checking prerequisites"

if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    Write-Err "hermes CLI not found. Install Hermes Agent first: https://hermes-agent.nousresearch.com/docs"
}
$pyCmd = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
if (-not (Get-Command $pyCmd -ErrorAction SilentlyContinue)) {
    Write-Err "Python not found. Install Python 3.6+ from https://python.org"
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Err "gh CLI not found. Install: winget install GitHub.cli  OR  https://cli.github.com"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "git not found. Install: winget install Git.Git"
}

Write-OK "hermes CLI found"
Write-OK "python: $(& $pyCmd --version 2>&1)"
Write-OK "gh: $(gh --version 2>&1 | Select-Object -First 1)"
Write-OK "git: $(git --version 2>&1)"

if (-not (Get-Command adr -ErrorAction SilentlyContinue)) {
    Write-Warn "adr-tools not found — ADR lifecycle disabled. Install: npm install -g adr-tools"
} else {
    Write-OK "adr-tools found"
}

# ── 2. Install the Panel ───────────────────────────────────────────
Write-Step "Installing hermes-panel"

if (Test-Path $PanelDir) {
    Write-OK "Panel repo exists — pulling latest"
    Push-Location $PanelDir
    try { git pull --ff-only 2>$null } finally { Pop-Location }
} else {
    Write-OK "Cloning hermes-panel to $PanelDir"
    git clone $PanelRepo $PanelDir
}

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$panelScript = "$PanelDir\hermes-panel"
$panelLink   = "$BinDir\hermes-panel"
if (-not (Test-Path $panelLink)) {
    try {
        New-Item -ItemType SymbolicLink -Path $panelLink -Target $panelScript -ErrorAction Stop | Out-Null
        Write-OK "Symlinked hermes-panel → $panelLink"
    } catch {
        Copy-Item $panelScript $panelLink
        Write-OK "Copied hermes-panel → $panelLink"
    }
} else {
    Write-OK "hermes-panel already linked in $BinDir"
}

# Ensure ~/bin in PATH
if ($env:Path -notlike "*$BinDir*") {
    $env:Path = "$BinDir;$env:Path"
    $currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentUserPath -notlike "*$BinDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$BinDir;$currentUserPath", "User")
        Write-OK "Added $BinDir to user PATH"
    }
}

# ── 3. Provider Configuration ──────────────────────────────────────
Write-Step "Provider Configuration"

# Provider catalog
$providers = @{
    deepseek   = @{ Label = "DeepSeek";                  KeyEnv = "DEEPSEEK_API_KEY";    SModel = "deepseek-v4-pro";      CModel = "deepseek-v4-flash";       TModel = "deepseek-v4-pro" }
    anthropic  = @{ Label = "Anthropic";                 KeyEnv = "ANTHROPIC_API_KEY";   SModel = "claude-opus-4-20250514"; CModel = "claude-sonnet-4-20250514"; TModel = "claude-opus-4-20250514" }
    openai     = @{ Label = "OpenAI";                    KeyEnv = "OPENAI_API_KEY";      SModel = "gpt-5";                  CModel = "gpt-4o";                   TModel = "gpt-5" }
    openrouter = @{ Label = "OpenRouter (multi-provider)"; KeyEnv = "OPENROUTER_API_KEY"; SModel = "deepseek/deepseek-chat";  CModel = "anthropic/claude-sonnet-4";  TModel = "deepseek/deepseek-chat" }
}

function Choose-Provider {
    param($Purpose, $Default = "deepseek", $ExcludeKey = $null)

    Write-Host ""
    Write-Host "  $Purpose"
    Write-Host "  ──────────────────────────────────────────"
    $i = 1
    $idx = @{}
    foreach ($key in @("deepseek", "anthropic", "openai", "openrouter")) {
        if ($key -ne $ExcludeKey) {
            Write-Host "    $i) $($providers[$key].Label)"
            $idx[$i] = $key
            $i++
        }
    }
    Write-Host ""

    while ($true) {
        Write-Prompt "Choose provider [1]:"
        $choice = Read-Host
        if ([string]::IsNullOrEmpty($choice)) { $choice = "1" }
        if ($idx.ContainsKey([int]$choice)) {
            return $idx[[int]$choice]
        }
        Write-Warn "Enter 1-$($i-1)"
    }
}

function Save-ApiKey {
    param($ProviderKey, $KeyEnv)

    # Already in shared.env?
    if ((Test-Path $sharedEnv) -and (Select-String -Path $sharedEnv -Pattern "^$KeyEnv=" -Quiet)) {
        Write-OK "$KeyEnv already set in shared.env"
        return
    }

    # Already in environment?
    if ([Environment]::GetEnvironmentVariable($KeyEnv)) {
        Write-OK "$KeyEnv found in environment"
        return
    }

    # Non-interactive?
    if (-not [Environment]::UserInteractive -or [Console]::IsInputRedirected) {
        Write-Warn "Non-interactive mode. Set $KeyEnv in your environment or shared.env"
        return
    }

    Write-Host ""
    $secureKey = Read-Host -AsSecureString -Prompt "→ Paste your $($providers[$ProviderKey].Label) API key"
    $keyValue = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    )

    if ([string]::IsNullOrEmpty($keyValue)) {
        Write-Warn "No key entered — profiles will need manual setup"
        return
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $sharedEnv -Parent) | Out-Null
    Add-Content -Path $sharedEnv -Value "$KeyEnv=$keyValue"
    Write-OK "$KeyEnv saved to $sharedEnv"
}

# Pick primary provider (interactive or default)
if ($host.UI.RawUI.WindowTitle -and -not [Console]::IsInputRedirected) {
    $PRIMARY = Choose-Provider "Primary provider for all 3 roles (strategist, coder, tech-lead):"
} else {
    $PRIMARY = "deepseek"
    Write-Warn "Non-interactive mode — using DeepSeek as primary"
}

Save-ApiKey $PRIMARY $providers[$PRIMARY].KeyEnv

$STRAT_MODEL = $providers[$PRIMARY].SModel
$CODER_MODEL = $providers[$PRIMARY].CModel
$TL_MODEL    = $providers[$PRIMARY].TModel

Write-Host ""
Write-OK "Primary: $($providers[$PRIMARY].Label)"
Write-Host "    strategist → $STRAT_MODEL"
Write-Host "    coder      → $CODER_MODEL"
Write-Host "    tech-lead  → $TL_MODEL"

# Optional secondary provider for nm
$SECONDARY = $null
if ($host.UI.RawUI.WindowTitle -and -not [Console]::IsInputRedirected) {
    Write-Host ""
    Write-Host "  Adversarial review (nm)"
    Write-Host "  ──────────────────────────────────────────"
    Write-Host "  nm catches model-family blind spots by using a DIFFERENT provider"
    Write-Host "  from the coder. Skip this and nm reviews use the same provider."
    Write-Host ""

    Write-Prompt "Add a secondary provider for nm? [y/N]:"
    $addSecondary = Read-Host
    if ($addSecondary -match '^[Yy]') {
        $SECONDARY = Choose-Provider "nm provider (must differ from $($providers[$PRIMARY].Label)):" -ExcludeKey $PRIMARY
        Save-ApiKey $SECONDARY $providers[$SECONDARY].KeyEnv
        Write-OK "nm provider: $($providers[$SECONDARY].Label)"
    } else {
        Write-Warn "Skipping secondary provider — nm will use $($providers[$PRIMARY].Label)"
    }
} else {
    Write-Warn "Non-interactive mode — skipping secondary provider"
}

# ── 4. Create Agent Profiles ───────────────────────────────────────
Write-Step "Creating agent profiles"

function New-HermesProfile {
    param($Name, $Model, $Provider)

    $profileList = hermes profile list 2>&1
    if ($profileList -match "\b$Name\b") {
        Write-OK "Profile '$Name' already exists"
    } else {
        Write-OK "Creating profile: $Name"
        hermes profile create $Name
    }

    hermes --profile $Name config set model.default $Model
    hermes --profile $Name config set model.provider $Provider
    hermes --profile $Name config set agent.max_turns 150
    hermes --profile $Name config set terminal.env_passthrough '[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]'

    if ($Name -eq "strategist") {
        hermes --profile $Name config set agent.reasoning_effort medium
    }

    Write-OK "Profile '$Name' configured ($Model @ $Provider)"
}

New-HermesProfile "strategist" $STRAT_MODEL $PRIMARY
New-HermesProfile "coder"      $CODER_MODEL $PRIMARY
New-HermesProfile "tech-lead"  $TL_MODEL    $PRIMARY

if ($SECONDARY) {
    $NM_MODEL = $providers[$SECONDARY].SModel
    New-HermesProfile "nm" $NM_MODEL $SECONDARY
}

# ── 5. Deploy Panel Skills ─────────────────────────────────────────
Write-Step "Deploying panel skills"

function Deploy-Skill {
    param($SkillName, $DestDir)

    $src  = "$PanelDir\skills\$SkillName"
    $dest = "$DestDir\$SkillName"

    if (-not (Test-Path $src)) {
        Write-Warn "Skill '$SkillName' not found in repo — skipping"
        return
    }

    if (Test-Path $dest) {
        Write-OK "Skill exists: $dest"
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        Copy-Item -Recurse $src $dest
        Write-OK "Deployed: $dest"
    }
}

$skillCategory = "software-development"
$stratDir = "$HermesHome\profiles\strategist\skills\$skillCategory"
$coderDir = "$HermesHome\profiles\coder\skills\$skillCategory"
$tlDir    = "$HermesHome\profiles\tech-lead\skills\$skillCategory"
$globDir  = "$HermesHome\skills\$skillCategory"

Deploy-Skill "spec-strategist-lite"          $stratDir
Deploy-Skill "ponytail-guard"                $stratDir
Deploy-Skill "ai-coding-best-practices-lite" $coderDir
Deploy-Skill "adversarial-review-lite"        $tlDir
Deploy-Skill "ponytail-guard"                $tlDir
Deploy-Skill "no-mistakes"                   $globDir

# ── 6. GitHub Token ────────────────────────────────────────────────
Write-Step "GitHub token"

if ((Test-Path $sharedEnv) -and (Select-String -Path $sharedEnv -Pattern "GH_TOKEN=" -Quiet)) {
    Write-OK "GH_TOKEN already set in shared.env"
} elseif ($host.UI.RawUI.WindowTitle -and -not [Console]::IsInputRedirected) {
    Write-Warn "GitHub token not found. Paste your token (needs 'repo' scope):"
    $secureToken = Read-Host -AsSecureString -Prompt "  GH_TOKEN"
    $tokenValue = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    )
    New-Item -ItemType Directory -Force -Path (Split-Path $sharedEnv -Parent) | Out-Null
    Add-Content -Path $sharedEnv -Value "GH_TOKEN=$tokenValue"
    Add-Content -Path $sharedEnv -Value "GITHUB_TOKEN=$tokenValue"
    Write-OK "Tokens written to $sharedEnv"
} else {
    Write-Warn "GH_TOKEN not set. Add manually to $sharedEnv"
}

# ── 7. Verify ──────────────────────────────────────────────────────
Write-Step "Verifying setup"

try {
    & $pyCmd -c "compile(open('$panelScript').read(), 'hermes-panel', 'exec')" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-OK "hermes-panel: syntax OK"
    } else {
        Write-Warn "hermes-panel syntax check failed"
    }
} catch {
    Write-Warn "Could not syntax-check hermes-panel: $_"
}

foreach ($profile in @("strategist", "coder", "tech-lead")) {
    $result = hermes --profile $profile -q "echo ok" --yolo 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Profile '$profile': responds OK"
    } else {
        Write-Warn "Profile '$profile': smoke test failed (check API key / provider config)"
    }
}

# ── Done ───────────────────────────────────────────────────────────
Write-Step "Setup complete"
Write-Host ""
Write-Host "  Profiles:"
Write-Host "    strategist  → $STRAT_MODEL ($($providers[$PRIMARY].Label))"
Write-Host "    coder       → $CODER_MODEL ($($providers[$PRIMARY].Label))"
Write-Host "    tech-lead   → $TL_MODEL ($($providers[$PRIMARY].Label))"
if ($SECONDARY) {
    Write-Host "    nm          → $NM_MODEL ($($providers[$SECONDARY].Label))"
} else {
    Write-Host "    nm          → same as coder (no secondary provider configured)"
}
Write-Host ""
Write-Host "  Next steps:"
Write-Host '  1. Add AGENTS.md to your project root (see docs/setup.md)'
Write-Host '  2. Run a smoke test:'
Write-Host '     cd ~/your-project'
Write-Host '     hermes-panel "Add a comment" .'
Write-Host '  3. Force full pipeline test:'
Write-Host '     $env:PANEL_FORCE_FULL = 1; hermes-panel "Add a health check" .'
Write-Host ""
Write-OK "Happy orchestrating! 🎭"
