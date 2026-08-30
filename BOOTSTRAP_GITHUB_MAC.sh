#!/usr/bin/env bash
set -euo pipefail

echo "== Upsilon GitHub bootstrap =="

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e .
pip install pytest

echo
echo "Running local tests..."
pytest -q test_executor.py test_schema.py test_persistence_plan.py

echo
echo "Local test bootstrap complete."
echo "Next: add your GitHub remote, commit, push, then verify CI."
