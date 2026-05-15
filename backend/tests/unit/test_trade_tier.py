"""Tests for trade-tier sibling normalization (pure logic, no DB)."""

from agente10.cnae.trade_tier import (
    _tier_for,
    normalize_to_fabricacao_first,
)

# CNAE codes used in scenarios (real codes from the Brazilian taxonomy):
FAB_CABOS = "2733300"  # Fabricação de cabos elétricos isolados
ATAC_MAT_ELETRICO = "4673700"  # Comércio atacadista de material elétrico
VAR_MAT_ELETRICO = "4744005"  # Comércio varejista de materiais elétricos

FAB_MOVEIS = "3101200"  # Fabricação de móveis com predominância de madeira
ATAC_MOVEIS = "4642701"  # Comércio atacadista de móveis
VAR_MOVEIS = "4754701"  # Comércio varejista de móveis

SERVICO_TI = "6209100"  # Suporte técnico em TI — outside C/46/47


def test_tier_for_division_ranges():
    assert _tier_for(FAB_CABOS) == "fabricacao"
    assert _tier_for(FAB_MOVEIS) == "fabricacao"
    assert _tier_for("1011200") == "fabricacao"  # divisão 10
    assert _tier_for("3399100") == "fabricacao"  # divisão 33
    assert _tier_for(ATAC_MAT_ELETRICO) == "atacado"
    assert _tier_for(VAR_MAT_ELETRICO) == "varejo"
    assert _tier_for(SERVICO_TI) is None
    assert _tier_for("4520001") is None  # divisão 45 (veículos) — não cobrimos
    assert _tier_for("") is None
    assert _tier_for("abc") is None


def test_primary_in_fabricacao_keeps_primary_and_adds_two_siblings():
    primary = FAB_CABOS
    secs = []
    siblings = {
        "fabricacao": FAB_CABOS,
        "atacado": ATAC_MAT_ELETRICO,
        "varejo": VAR_MAT_ELETRICO,
    }
    p, s = normalize_to_fabricacao_first(primary, secs, siblings)
    assert p == FAB_CABOS
    assert ATAC_MAT_ELETRICO in s
    assert VAR_MAT_ELETRICO in s
    assert FAB_CABOS not in s  # primary never duplicated


def test_primary_in_atacado_swaps_to_fabricacao():
    primary = ATAC_MOVEIS
    secs = []
    siblings = {
        "atacado": ATAC_MOVEIS,
        "fabricacao": FAB_MOVEIS,
        "varejo": VAR_MOVEIS,
    }
    p, s = normalize_to_fabricacao_first(primary, secs, siblings)
    assert p == FAB_MOVEIS, "fabricacao should be promoted to primary"
    assert ATAC_MOVEIS in s, "original primary demoted to secondary"
    assert VAR_MOVEIS in s
    assert FAB_MOVEIS not in s


def test_primary_in_varejo_swaps_to_fabricacao_and_demotes_varejo():
    primary = VAR_MOVEIS
    secs = []
    siblings = {
        "varejo": VAR_MOVEIS,
        "fabricacao": FAB_MOVEIS,
        "atacado": ATAC_MOVEIS,
    }
    p, s = normalize_to_fabricacao_first(primary, secs, siblings)
    assert p == FAB_MOVEIS
    assert VAR_MOVEIS in s
    assert ATAC_MOVEIS in s


def test_no_siblings_above_threshold_returns_unchanged():
    primary = FAB_CABOS
    secs = ["1234567"]  # something curator added
    siblings = {
        "fabricacao": FAB_CABOS,
        "atacado": None,
        "varejo": None,
    }
    p, s = normalize_to_fabricacao_first(primary, secs, siblings)
    assert p == FAB_CABOS
    assert s == ["1234567"]


def test_primary_outside_section_c_or_g46_47_returns_unchanged():
    # Empty siblings dict means caller detected primary is not in any tier
    p, s = normalize_to_fabricacao_first(SERVICO_TI, [VAR_MAT_ELETRICO], {})
    assert p == SERVICO_TI
    assert s == [VAR_MAT_ELETRICO]


def test_curator_secondaries_preserved_alongside_auto_suggested():
    primary = FAB_CABOS
    curator_secs = ["8888888", "9999999"]
    siblings = {
        "fabricacao": FAB_CABOS,
        "atacado": ATAC_MAT_ELETRICO,
        "varejo": VAR_MAT_ELETRICO,
    }
    p, s = normalize_to_fabricacao_first(primary, curator_secs, siblings)
    assert p == FAB_CABOS
    # Curator's picks come first; auto-suggestions appended afterward
    assert s[0] == "8888888"
    assert s[1] == "9999999"
    assert ATAC_MAT_ELETRICO in s
    assert VAR_MAT_ELETRICO in s


def test_secondary_list_capped_at_max():
    primary = FAB_CABOS
    curator_secs = ["1111111", "2222222", "3333333", "4444444", "5555555"]
    siblings = {
        "fabricacao": FAB_CABOS,
        "atacado": ATAC_MAT_ELETRICO,
        "varejo": VAR_MAT_ELETRICO,
    }
    p, s = normalize_to_fabricacao_first(primary, curator_secs, siblings)
    assert len(s) <= 4


def test_swap_demotes_original_before_curator_secs():
    primary = ATAC_MAT_ELETRICO
    curator_secs = ["8888888"]
    siblings = {
        "atacado": ATAC_MAT_ELETRICO,
        "fabricacao": FAB_CABOS,
        "varejo": VAR_MAT_ELETRICO,
    }
    p, s = normalize_to_fabricacao_first(primary, curator_secs, siblings)
    assert p == FAB_CABOS
    # Demoted original primary comes first so the relationship survives capping
    assert s[0] == ATAC_MAT_ELETRICO
