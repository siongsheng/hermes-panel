# ───────────────────────────────────────────────────────────────────
# Hermes Panel — Windows PC Setup
# One-time machine setup. Idempotent — safe to re-run.
# Usage: Right-click → "Run with PowerShell" or:
#        powershell -ExecutionPolicy Bypass -File setup-windows.ps1
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

# ── 1. Prerequisites Check ─────────────────────────────────────────
Write-Step "Checking prerequisites"

# hermes
if (Get-Command hermes -ErrorAction SilentlyContinue) {
    Write-OK "hermes CLI found"
} else {
    Write-Err "hermes CLI not found. Install Hermes Agent first: https://hermes-agent.nousresearch.com/docs"
}

# python3
if (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pyVer = python3 --version 2>&1
    Write-OK "python3: $pyVer"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python --version 2>&1
    Write-OK "python: $pyVer"
    # Create a python3 alias or note it
    Write-Warn "No 'python3' command — the panel expects 'python3'. Consider: New-Item -Path `"$BinDir\python3.cmd`" -Value '@python %*' -Force"
} else {
    Write-Err "Python not found. Install Python 3.6+ from https://python.org"
}

# gh CLI
if (Get-Command gh -ErrorAction SilentlyContinue) {
    Write-OK "gh CLI found"
} else {
    Write-Err "gh CLI not found. Install: winget install GitHub.cli  OR  https://cli.github.com"
}

# git
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVer = git --version 2>&1
    Write-OK "git: $gitVer"
} else {
    Write-Err "git not found. Install: winget install Git.Git"
}

# adr-tools (optional — Windows version via npm or choco)
if (Get-Command adr -ErrorAction SilentlyContinue) {
    Write-OK "adr-tools found"
} elseif (Get-Command npx -ErrorAction SilentlyContinue) {
    Write-Warn "adr-tools not found. Install via: npm install -g adr-tools"
} else {
    Write-Warn "adr-tools not found — ADR lifecycle disabled. Install: npm install -g adr-tools"
}

# ── 2. Install the Panel ───────────────────────────────────────────
Write-Step "Installing hermes-panel"

if (Test-Path $PanelDir) {
    Write-OK "Panel repo exists — pulling latest"
    Push-Location $PanelDir
    try {
        git pull --ff-only 2>$null
        if ($LASTEXITCODE -ne 0) { Write-Warn "Pull failed (dirty tree?). Continuing with existing clone." }
    } finally { Pop-Location }
} else {
    Write-OK "Cloning hermes-panel to $PanelDir"
    git clone $PanelRepo $PanelDir
    if ($LASTEXITCODE -ne 0) { Write-Err "Clone failed" }
}

# Copy panel script to ~/bin (Windows: no symlinks by default without admin)
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$panelScript = "$PanelDir\hermes-panel"
$panelLink   = "$BinDir\hermes-panel"

if (Test-Path $panelLink) {
    Write-OK "hermes-panel already in $BinDir"
} else {
    # Try symlink first (requires admin or developer mode), fall back to copy
    try {
        New-Item -ItemType SymbolicLink -Path $panelLink -Target $panelScript -ErrorAction Stop | Out-Null
        Write-OK "Symlinked hermes-panel → $panelLink"
    } catch {
        Copy-Item $panelScript $panelLink
        Write-OK "Copied hermes-panel → $panelLink (symlink requires admin/dev mode)"
    }
}

# Ensure ~/bin is in PATH for this session (and persist if possible)
$binInPath = ($env:Path -split ';') -contains $BinDir
if (-not $binInPath) {
    $env:Path = "$BinDir;$env:Path"
    # Persist to user PATH
    $currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentUserPath -notlike "*$BinDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$BinDir;$currentUserPath", "User")
        Write-OK "Added $BinDir to user PATH"
    }
}

# ── 3. Create Agent Profiles ───────────────────────────────────────
Write-Step "Creating agent profiles"

function New-HermesProfile {
    param($Name, $Model)

    $profileList = hermes profile list 2>&1
    if ($profileList -match "\b$Name\b") {
        Write-OK "Profile '$Name' already exists"
    } else {
        Write-OK "Creating profile: $Name"
        hermes profile create $Name
    }

    # Override specific config values (profile create gives full defaults)
    hermes --profile $Name config set model.default $Model
    hermes --profile $Name config set model.provider deepseek
    hermes --profile $Name config set agent.max_turns 150
    hermes --profile $Name config set terminal.env_passthrough '[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]'

    if ($Name -eq "strategist") {
        hermes --profile $Name config set agent.reasoning_effort medium
    }

    Write-OK "Profile '$Name' configured ($Model)"
}

New-HermesProfile "strategist" "deepseek-v4-pro"
New-HermesProfile "coder"      "deepseek-v4-flash"
New-HermesProfile "tech-lead"  "deepseek-v4-pro"

# ── 4. Deploy Panel Skills ─────────────────────────────────────────
Write-Step "Deploying panel skills"

function Deploy-Skill {
    param($SkillName, $DestDir)

    $src  = "$PanelDir\skills\$SkillName"
    $dest = "$DestDir\$SkillName"

    if (-not (Test-Path $src)) {
        Write-Warn "Skill '$SkillName' not found in repo — skipping (may have been removed)"
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

# ── 5. GitHub Token ────────────────────────────────────────────────
Write-Step "GitHub token"

$sharedEnv = "$HermesHome\shared.env"

if ((Test-Path $sharedEnv) -and (Select-String -Path $sharedEnv -Pattern "GH_TOKEN=" -SimpleMatch -Quiet)) {
    Write-OK "GH_TOKEN already set in shared.env"
} else {
    Write-Warn "GitHub token not found. Paste your token (needs 'repo' scope):"
    $secureToken = Read-Host -AsSecureString -Prompt "  GH_TOKEN"
    $tokenValue = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    )
    New-Item -ItemType Directory -Force -Path (Split-Path $sharedEnv -Parent) | Out-Null
    Add-Content -Path $sharedEnv -Value "GH_TOKEN=$tokenValue"
    Add-Content -Path $sharedEnv -Value "GITHUB_TOKEN=$tokenValue"
    Write-OK "Tokens written to $sharedEnv"
}

# ── 6. Verify ──────────────────────────────────────────────────────
Write-Step "Verifying setup"

# Syntax-check the panel script
try {
    $pyCmd = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
    & $pyCmd -c "compile(open('$panelScript').read(), 'hermes-panel', 'exec')" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-OK "hermes-panel: syntax OK"
    } else {
        Write-Warn "hermes-panel syntax check failed (may still work — check output above)"
    }
} catch {
    Write-Warn "Could not syntax-check hermes-panel: $_"
}

# Quick profile smoke tests
foreach ($profile in @("strategist", "coder", "tech-lead")) {
    $result = hermes --profile $profile -q "echo ok" --yolo 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Profile '$profile': responds OK"
    } else {
        Write-Warn "Profile '$profile': smoke test failed — check API key / provider config"
    }
}

# ── Done ───────────────────────────────────────────────────────────
Write-Step "Setup complete"
Write-Host ""
Write-Host "  Next steps:"
Write-Host "  1. Add AGENTS.md to your project root (see docs/setup.md ┬º3.1)"
Write-Host "  2. Run a smoke test:"
Write-Host "     cd ~/your-project"
Write-Host "     hermes-panel `"Add a comment`" ."
Write-Host "  3. Force full pipeline test:"
Write-Host "     `$env:PANEL_FORCE_FULL = 1; hermes-panel `"Add a health check`" ."
Write-Host ""
Write-OK "Happy orchestrating! 🎭"
