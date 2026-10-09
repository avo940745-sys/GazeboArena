#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  if command -v uv >/dev/null; then
    uv venv --python 3.10 .venv
  else
    python3 -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)' || {
      echo 'Editor requires Python 3.10–3.13; install a supported Python or uv.' >&2
      exit 2
    }
    python3 -m venv .venv
  fi
fi
.venv/bin/python -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)' || {
  echo 'Existing .venv needs Python 3.10–3.13 for the editor.' >&2
  exit 2
}
if command -v uv >/dev/null; then
  uv pip install --python .venv/bin/python -e '.[gui]'
else
  .venv/bin/python -m pip install -e '.[gui]'
fi
if [[ "${1:-}" != "--no-run" ]]; then
  exec .venv/bin/gazeboarena edit
fi
