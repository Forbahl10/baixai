#!/bin/sh
# Atalho para macOS/Linux; a lógica está em scripts/package_helper.py (multiplataforma).
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
exec "${PYTHON:-.venv/bin/python}" scripts/package_helper.py --source "$@"
