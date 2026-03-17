#!/usr/bin/env bash
# JLAW Agent Platform v5.0 — Local Machine Setup (Unix/macOS/WSL)
# Run: chmod +x setup.sh && ./setup.sh

set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  JLAW Agent Platform v5.0 — Setup               ║"
echo "║  Local machine deployment                        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── Check Python ───
echo "[1/6] Checking Python version..."
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

# ─── Create virtual environment ───
echo "[2/6] Creating Python virtual environment..."
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
echo "[3/6] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "  ✓ Dependencies installed"

# ─── Install Claude Agent SDK ───
echo "[4/6] Installing Claude Agent SDK..."
pip install --quiet claude-agent-sdk 2>/dev/null || echo "  ⚠ claude-agent-sdk not available — direct execution mode will be used"
echo "  ✓ Agent SDK step complete"

# ─── Environment file ───
echo "[5/6] Setting up environment..."
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
echo "[6/6] Initializing data pipeline..."
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
