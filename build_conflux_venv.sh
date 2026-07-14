#!/usr/bin/env bash
# Build the named project venv (conflux_venv) from requirements.txt.
#
# Named so the active environment is visible in the terminal prompt:
#   source conflux_venv/bin/activate   ->  (conflux-atlas) user@host$
#
# Idempotent: re-running upgrades pip and re-syncs requirements into the
# existing venv. Override the interpreter with PYTHON=python3.12 etc.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON="${PYTHON:-python3}"
VENV_DIR="conflux_venv"

echo "🐍 interpreter: $($PYTHON --version 2>&1) ($(command -v "$PYTHON"))"
"$PYTHON" -m venv --prompt conflux-atlas "$VENV_DIR"

"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r requirements.txt -r requirements-dev.txt

echo
echo "✅ $VENV_DIR ready. Activate with:"
echo "   source $VENV_DIR/bin/activate"
"$VENV_DIR/bin/python" -c "import pydantic, pypdf; print('   pydantic', pydantic.__version__, '· pypdf', pypdf.__version__)"
