#!/usr/bin/env bash
# SLAC installer — installs the `slac` CLI.
#
#   curl -fsSL https://raw.githubusercontent.com/ramanshrivastava/slac/main/install.sh | bash
#
# Prefers pipx (isolated); falls back to `pip install --user`. If run from a
# clone, installs that working tree; otherwise installs `slac` from PyPI.
set -euo pipefail

PKG="slac"
SRC="$PKG"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/pyproject.toml" ]; then
  SRC="$SELF_DIR"   # running from a clone — install this tree
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 (>=3.8) is required" >&2
  exit 1
fi

echo "Installing SLAC from: $SRC"
if command -v pipx >/dev/null 2>&1; then
  pipx install --force "$SRC"
elif python3 -m pipx --version >/dev/null 2>&1; then
  python3 -m pipx install --force "$SRC"
else
  echo "pipx not found — falling back to 'pip install --user'"
  python3 -m pip install --user "$SRC"
fi

echo
echo "Done. Try:  slac --version"
echo "If 'slac' isn't found, add your user bin dir to PATH (e.g. 'pipx ensurepath')."
