#!/usr/bin/env bash
# JLAW Agent Platform v5.0 — Local Machine Setup
# Run: chmod +x setup.sh && ./setup.sh

set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  JLAW Agent Platform v5.0 — Setup               ║"
echo "║  Local machine deployment                        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── Check Python ───
echo "[1/7] Checking Python version..."
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "  ✗ Python not found. Install Python 3.10+ and try again."
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  ✓ Found $PYTHON_CMD $PY_VERSION"

PY_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo "  ✗ Python 3.10+ required. Found $PY_VERSION."
    exit 1
fi

# ─── Check Node.js ───
echo "[2/7] Checking Node.js..."
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    echo "  ✓ Found Node.js $NODE_VERSION"
else
    echo "  ⚠ Node.js not found. Required for Claude Agent SDK CLI."
    echo "    Install from: https://nodejs.org/ (v18+)"
    echo "    Or: curl -fsSL https://claude.ai/install.sh | bash"
fi

# ─── Create virtual environment ───
echo "[3/7] Creating Python virtual environment..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
    echo "  ✓ Created .venv"
else
    echo "  ✓ .venv already exists"
fi

# Activate
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
echo "  ✓ Activated virtual environment"

# ─── Install dependencies ───
echo "[4/7] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "  ✓ Dependencies installed"

# ─── Install Claude Agent SDK ───
echo "[5/7] Installing Claude Agent SDK..."
pip install --quiet claude-agent-sdk
echo "  ✓ Claude Agent SDK installed"

# ─── Environment file ───
echo "[6/7] Setting up environment..."
if [ ! -f ".env" ]; then
    cp config/.env.template .env
    echo "  ✓ Created .env from template"
    echo ""
    echo "  ⚠ IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY"
    echo "    nano .env"
    echo ""
else
    echo "  ✓ .env already exists"
fi

# ─── Initialize data pipeline ───
echo "[7/7] Initializing data pipeline..."
$PYTHON_CMD scripts/init_data_pipeline.py
echo ""

# ─── Summary ───
echo "╔══════════════════════════════════════════════════╗"
echo "║  Setup complete!                                 ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  Next steps:                                     ║"
echo "║  1. Edit .env with your ANTHROPIC_API_KEY        ║"
echo "║  2. Copy EDGAR files → data/raw-edgar/           ║"
echo "║  3. Copy 36 DOCX reports → data/deliverables/    ║"
echo "║  4. (Optional) Install Proton Bridge for Phase 4 ║"
echo "║                                                  ║"
echo "║  Then run:                                       ║"
echo "║    python run.py status     # Check readiness    ║"
echo "║    python run.py pipeline   # Full run           ║"
echo "║    python run.py interactive # Chat mode         ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
