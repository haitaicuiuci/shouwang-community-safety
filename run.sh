#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
if [[ -n "${PYTHON:-}" ]]; then PY="$PYTHON"; elif [[ -x .venv/bin/python ]]; then PY="$PWD/.venv/bin/python"; else PY=python3; fi
case "${1:-reproduce}" in
 demo) "$PY" -m http.server "${PORT:-8765}" --bind 127.0.0.1 --directory web ;;
 setup)
  "$PY" -c 'import sys; assert sys.version_info >= (3,10), "Use Python 3.10+ (validated on 3.12)"'
  "$PY" -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt ;;
 reproduce)
  "$PY" -c 'import sklearn,numpy,scipy' || { echo 'Run PYTHON=python3.12 ./run.sh setup first'; exit 1; }
  "$PY" src/download.py
  "$PY" src/pipeline.py
  "$PY" src/report.py
  "$PY" -m unittest discover -s tests -v ;;
 http-check) "$PY" tests/check_http.py ;;
 verify) "$PY" -m unittest discover -s tests -v ;;
 serve) "$PY" src/serve.py --port "${PORT:-8765}" ;;
 *) echo 'Usage: ./run.sh {setup|reproduce|verify|http-check|serve|demo}'; exit 1 ;;
esac
