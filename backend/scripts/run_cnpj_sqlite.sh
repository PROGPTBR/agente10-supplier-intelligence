#!/usr/bin/env bash
# Wrapper for rictom/cnpj-sqlite.
#
# Downloads the latest Receita Federal CNPJ open data, parses it via the upstream
# tool, and produces backend/data/cnpj.db (~30GB).
#
# Idempotent: re-running pulls latest upstream + regenerates the SQLite. Existing
# cnpj.db is overwritten.
#
# Requires: bash, git, python3 (with venv), ~60GB free disk.
# Runtime: 1-2h on a modern laptop SSD.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data"
CACHE_DIR="${CNPJ_SQLITE_CACHE:-$DATA_DIR/cnpj_sqlite_cache}"
TARGET_DB="$DATA_DIR/cnpj.db"

mkdir -p "$DATA_DIR"

echo "==> rictom/cnpj-sqlite cache: $CACHE_DIR"
if [ ! -d "$CACHE_DIR/.git" ]; then
    git clone --depth 1 https://github.com/rictom/cnpj-sqlite.git "$CACHE_DIR"
else
    git -C "$CACHE_DIR" pull --ff-only
fi

cd "$CACHE_DIR"

echo "==> Setting up Python venv inside $CACHE_DIR/.venv"
python3 -m venv .venv

# venv binary directory: Windows uses Scripts/, Unix uses bin/
if [ -d ".venv/Scripts" ]; then
    VENV_BIN=".venv/Scripts"
else
    VENV_BIN=".venv/bin"
fi

# Use `python -m pip` rather than the pip executable directly: on Windows the
# pip.exe locks itself when invoked, so a `pip install --upgrade pip` fails. The
# `python -m` form sidesteps the lock and also doesn't require us to upgrade pip
# ourselves — stock venv pip is fine for rictom's requirements.txt.
"$VENV_BIN/python" -m pip install --quiet -r requirements.txt

# rictom's entry script. As of v0.7 (mar/2026) the script that runs the full
# pipeline is `dados_cnpj_baixar_e_processar_v07.py`. The exact name may drift —
# the loop below picks the most recent `dados_cnpj_*.py` matcher.
ENTRY=$(ls -t dados_cnpj_*.py 2>/dev/null | head -n1 || true)
if [ -z "$ENTRY" ]; then
    echo "ERROR: could not locate rictom entry script in $CACHE_DIR" >&2
    echo "Expected file matching dados_cnpj_*.py" >&2
    exit 1
fi
echo "==> Running upstream pipeline: $ENTRY (this takes 1-2h)"
"$VENV_BIN/python" "$ENTRY"

# Upstream writes cnpj.db into its own directory. Move it into our data dir.
if [ ! -f cnpj.db ]; then
    echo "ERROR: upstream did not produce cnpj.db in $CACHE_DIR" >&2
    exit 1
fi

mv cnpj.db "$TARGET_DB"
SIZE=$(du -h "$TARGET_DB" | cut -f1)
echo "==> OK — wrote $TARGET_DB ($SIZE)"
