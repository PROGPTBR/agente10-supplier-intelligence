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

# rictom's pipeline has two sequential scripts (verified against repo v0.7+):
#   1) dados_cnpj_baixa.py        — downloads RF ZIP files into dados-publicos-zip/
#   2) dados_cnpj_para_sqlite.py  — parses the ZIPs into cnpj.db
# (A third optional script `dados_cnpj_cnae_secundaria.py` builds a normalized
#  secondary-CNAE index table — our transform reads est.cnae_fiscal_secundaria
#  directly, so we skip it.)
#
# Both scripts have interactive input() prompts ("Deseja prosseguir?",
# "Pressione Enter"). We pipe `yes` to auto-confirm everything. The download
# step also asks to wipe existing files on re-run — which is what we want for
# idempotent monthly refresh.
for ENTRY in dados_cnpj_baixa.py dados_cnpj_para_sqlite.py; do
    if [ ! -f "$ENTRY" ]; then
        echo "ERROR: upstream script $ENTRY missing in $CACHE_DIR" >&2
        echo "Has rictom/cnpj-sqlite layout changed?" >&2
        exit 1
    fi
    echo "==> Running upstream: $ENTRY"
    # Temporarily disable pipefail so `yes` getting SIGPIPE'd at end of pipeline
    # doesn't fail the whole script — we only care about the Python script's RC.
    set +o pipefail
    yes | "$VENV_BIN/python" "$ENTRY"
    python_rc=$?
    set -o pipefail
    if [ "$python_rc" -ne 0 ]; then
        echo "ERROR: $ENTRY exited with code $python_rc" >&2
        exit "$python_rc"
    fi
done

# Upstream writes cnpj.db into its own directory. Move it into our data dir.
if [ ! -f cnpj.db ]; then
    echo "ERROR: upstream did not produce cnpj.db in $CACHE_DIR" >&2
    exit 1
fi

mv cnpj.db "$TARGET_DB"
SIZE=$(du -h "$TARGET_DB" | cut -f1)
echo "==> OK — wrote $TARGET_DB ($SIZE)"
