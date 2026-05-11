import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agente10.utils import cnpj as cnpj_mod
from agente10.utils.cnpj import (
    gerar_cnpj_alfanum_valido,
    limpar_cnpj,
    validar_cnpj_dv,
)

# Known-valid legacy (numeric-only) CNPJs of well-known public companies.
KNOWN_VALID_LEGACY = [
    "00000000000191",  # Banco do Brasil
    "33000167000101",  # Petrobras
    "60701190000104",  # Itaú
    "47960950000121",  # Magazine Luiza
    "33592510000154",  # Vale
]


@pytest.mark.parametrize("cnpj", KNOWN_VALID_LEGACY)
def test_known_valid_legacy_cnpjs(cnpj: str) -> None:
    assert validar_cnpj_dv(cnpj) is True


@pytest.mark.parametrize(
    "cnpj",
    [
        "00000000000192",  # wrong last digit
        "33000167000100",  # wrong DV
        "1234567890123",  # 13 chars
        "123456789012345",  # 15 chars
        "ABCDEFGHIJKLMN",  # all letters (DVs must be 0-9, so fails)
        "",  # empty
        "00.000.000/0001-92",  # formatted, wrong DV
    ],
)
def test_known_invalid_cnpjs(cnpj: str) -> None:
    assert validar_cnpj_dv(cnpj) is False


def test_limpar_cnpj_removes_punctuation() -> None:
    assert limpar_cnpj("00.000.000/0001-91") == "00000000000191"
    assert limpar_cnpj(" 00 000 000 0001 91 ") == "00000000000191"
    assert limpar_cnpj("ab-12.cd/ef34-gh") == "AB12CDEF34GH"


def test_validar_accepts_formatted() -> None:
    assert validar_cnpj_dv("00.000.000/0001-91") is True


def test_gerar_cnpj_produces_valid_cnpj() -> None:
    cnpj = gerar_cnpj_alfanum_valido()
    assert len(cnpj) == 14
    assert validar_cnpj_dv(cnpj) is True


@pytest.mark.parametrize("_", range(200))
def test_gerar_cnpj_always_valid(_: int) -> None:
    cnpj = gerar_cnpj_alfanum_valido()
    assert validar_cnpj_dv(cnpj) is True, f"Generated invalid CNPJ: {cnpj}"


@given(
    s=st.text(
        alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        min_size=14,
        max_size=14,
    )
)
@settings(max_examples=500, deadline=None)
def test_validator_never_raises_on_well_formed_input(s: str) -> None:
    result = validar_cnpj_dv(s)
    assert isinstance(result, bool)


@given(s=st.text(min_size=0, max_size=20))
@settings(max_examples=200, deadline=None)
def test_validator_handles_garbage(s: str) -> None:
    result = validar_cnpj_dv(s)
    assert isinstance(result, bool)


def test_validar_rejects_non_string() -> None:
    # type: ignore[arg-type] usage covers the isinstance guard
    assert validar_cnpj_dv(None) is False  # type: ignore[arg-type]
    assert validar_cnpj_dv(12345678901234) is False  # type: ignore[arg-type]


def test_calcular_dv_helper_raises_on_wrong_length() -> None:
    with pytest.raises(ValueError, match="12 chars"):
        cnpj_mod._calcular_dv_modulo11_alfanum("123")


def test_calcular_dv_helper_raises_on_invalid_char() -> None:
    # 12 chars but contains a lowercase/non-allowed char
    with pytest.raises(ValueError, match="Invalid char"):
        cnpj_mod._calcular_dv_modulo11_alfanum("00000000000a")
