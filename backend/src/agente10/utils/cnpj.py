"""CNPJ alfanumérico (jul/2026) validator and helpers.

Algorithm: each char's value = ord(c) - 48 (so '0'..'9' -> 0..9 and 'A'..'Z' -> 17..42).
Module 11 with weights [5,4,3,2,9,8,7,6,5,4,3,2] (DV1) and
[6,5,4,3,2,9,8,7,6,5,4,3,2] (DV2). DVs are always numeric (0-9).
"""

from __future__ import annotations

import random
import re

_ALLOWED_BASE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DV1_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_DV2_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PUNCTUATION = re.compile(r"[^0-9A-Za-z]")


def limpar_cnpj(s: str) -> str:
    """Strip punctuation/whitespace and upper-case alpha chars."""
    return _PUNCTUATION.sub("", s).upper()


def _char_value(c: str) -> int:
    """ord(c) - 48 for the alphanumeric CNPJ algorithm."""
    return ord(c) - 48


def _calcular_dv_modulo11_alfanum(base12: str) -> str:
    """Calculate the two check digits for a 12-char alphanumeric base.

    Returns a 2-char string of digits (DV1 + DV2). Raises ValueError on
    malformed input.
    """
    if len(base12) != 12:
        raise ValueError(f"Base must be 12 chars, got {len(base12)}")
    for c in base12:
        if c not in _ALLOWED_BASE_CHARS:
            raise ValueError(f"Invalid char in base: {c!r}")

    soma_dv1 = sum(_char_value(c) * w for c, w in zip(base12, _DV1_WEIGHTS, strict=True))
    rem1 = soma_dv1 % 11
    dv1 = 0 if rem1 < 2 else 11 - rem1

    base13 = base12 + str(dv1)
    soma_dv2 = sum(_char_value(c) * w for c, w in zip(base13, _DV2_WEIGHTS, strict=True))
    rem2 = soma_dv2 % 11
    dv2 = 0 if rem2 < 2 else 11 - rem2

    return f"{dv1}{dv2}"


def validar_cnpj_dv(cnpj: str) -> bool:
    """Validate the two check digits of a CNPJ.

    Accepts formatted (XX.XXX.XXX/XXXX-XX) or raw 14 chars.
    Accepts legacy numeric-only and new alphanumeric (jul/2026) formats.
    DVs (last 2 chars) must be digits.
    Returns False for any malformed input — never raises.
    """
    if not isinstance(cnpj, str):
        return False
    cleaned = limpar_cnpj(cnpj)
    if len(cleaned) != 14:
        return False
    base = cleaned[:12]
    dv_informed = cleaned[12:]

    if not dv_informed.isdigit():
        return False

    try:
        dv_calc = _calcular_dv_modulo11_alfanum(base)
    except ValueError:
        return False
    return dv_informed == dv_calc


def gerar_cnpj_alfanum_valido(rng: random.Random | None = None) -> str:
    """Generate a random valid alphanumeric CNPJ (jul/2026 format).

    For seeds, fixtures, and property-based tests. Not cryptographic.
    """
    r = rng or random.Random()
    base = "".join(r.choices(_ALLOWED_BASE_CHARS, k=12))
    return base + _calcular_dv_modulo11_alfanum(base)
