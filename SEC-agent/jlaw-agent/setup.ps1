# JLAW Agent Platform v5.0 — Local Machine Setup (Windows PowerShell)
# Run: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  JLAW Agent Platform v5.0 — Setup               ║" -ForegroundColor Cyan
Write-Host "║  Local machine deployment (Windows)              ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── Check Python ───
Write-Host "[1/6] Checking Python version..." -ForegroundColor Yellow
$PythonCmd = $null
try {
    $ver = & python --version 2>&1
    if ($ver -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -ge 3 -and $minor -ge 10) {
            $PythonCmd = "python"
            Write-Host "  ✓ Found python $ver" -ForegroundColor Green
        } else {
            Write-Host "  ✗ Python 3.10+ required. Found $ver." -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "  ✗ Python not found. Install Python 3.10+ from https://python.org" -ForegroundColor Red
    exit 1
}

if (-not $PythonCmd) {
    Write-Host "  ✗ Could not determine Python version." -ForegroundColor Red
    exit 1
}

# ─── Create virtual environment ───
Write-Host "[2/6] Creating Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    & $PythonCmd -m venv .venv
    Write-Host "  ✓ Created .venv" -ForegroundColor Green
} else {
    Write-Host "  ✓ .venv already exists" -ForegroundColor Green
}

# Activate
$ActivateScript = Join-Path (Get-Location) ".venv\Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    & $ActivateScript
    Write-Host "  ✓ Activated virtual environment" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Could not find activation script at $ActivateScript" -ForegroundColor Yellow
    Write-Host "    Continuing with system Python..." -ForegroundColor Yellow
}

# ─── Install dependencies ───
Write-Host "[3/6] Installing Python dependencies..." -ForegroundColor Yellow
& pip install --quiet --upgrade pip 2>$null
& pip install --quiet -r requirements.txt
Write-Host "  ✓ Dependencies installed" -ForegroundColor Green

# ─── Install Claude Agent SDK ───
Write-Host "[4/6] Installing Claude Agent SDK..." -ForegroundColor Yellow
try {
    & pip install --quiet claude-agent-sdk 2>$null
    Write-Host "  ✓ Claude Agent SDK installed" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ claude-agent-sdk not available — direct execution mode will be used" -ForegroundColor Yellow
}

# ─── Environment file ───
Write-Host "[5/6] Setting up environment..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item "config\.env.template" ".env"
    Write-Host "  ✓ Created .env from template" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ⚠ IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY" -ForegroundColor Yellow
    Write-Host "    notepad .env" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "  ✓ .env already exists" -ForegroundColor Green
}

# ─── Initialize data pipeline ───
Write-Host "[6/6] Initializing data pipeline..." -ForegroundColor Yellow
& $PythonCmd scripts\init_data_pipeline.py
Write-Host ""

# ─── Summary ───
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Setup complete!                                 ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║                                                  ║" -ForegroundColor Cyan
Write-Host "║  Next steps:                                     ║" -ForegroundColor Cyan
Write-Host "║  1. Edit .env with your ANTHROPIC_API_KEY        ║" -ForegroundColor Cyan
Write-Host "║  2. Copy EDGAR files → data\raw-edgar\           ║" -ForegroundColor Cyan
Write-Host "║  3. Copy 36 DOCX reports → data\deliverables\    ║" -ForegroundColor Cyan
Write-Host "║  4. (Optional) Install Proton Bridge for Phase 4 ║" -ForegroundColor Cyan
Write-Host "║                                                  ║" -ForegroundColor Cyan
Write-Host "║  Then run:                                       ║" -ForegroundColor Cyan
Write-Host "║    python run.py status     # Check readiness    ║" -ForegroundColor Cyan
Write-Host "║    python run.py pipeline   # Full run           ║" -ForegroundColor Cyan
Write-Host "║    python run.py interactive # Chat mode         ║" -ForegroundColor Cyan
Write-Host "║                                                  ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
