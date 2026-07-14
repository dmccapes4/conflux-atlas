#!/usr/bin/env bash
# Launch Conflux Atlas in its virtualenv.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi

# Ensure pygame is present (requirements may predate the demo).
./.venv/bin/python -c "import pygame" 2>/dev/null || ./.venv/bin/pip install 'pygame>=2.6'

exec ./.venv/bin/python main.py "$@"
