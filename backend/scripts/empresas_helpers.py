"""Pure helpers used by load_empresas.py during the RF transform.

Kept separate from load_empresas.py so they can be imported and unit-tested
without pulling in asyncpg.
"""

from __future__ import annotations

from datetime import date

# Receita Federal porte_empresa code → bucket
# Reference: layout PDF, table "Porte da Empresa" (5 codes).
_PORTE = {
    "01": "ME",      # Micro Empresa
    "03": "EPP",     # Empresa de Pequeno Porte
    "05": "DEMAIS",  # Demais (não enquadradas como ME/EPP)
}


def parse_porte(code: str | None) -> str | None:
    """Map RF porte_empresa code to a short bucket label. Unknown → None."""
    if not code:
        return None
    return _PORTE.get(code)


def parse_yyyymmdd(s: str | None) -> date | None:
    """Parse RF date strings in YYYYMMDD form. Empty/zero/malformed → None.

    RF marks "missing" data with `00000000` so this is non-defensive — empty,
    None, zero, or unparseable inputs all return None.
    """
    if not s or s == "00000000" or len(s) != 8:
        return None
    try:
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None
