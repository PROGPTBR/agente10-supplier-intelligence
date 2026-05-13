"""Integration tests for empresas discovery (find_empresas_by_cnae).

Shape tests use synthetic fixture (cnpj_synthetic.sql) so they run in CI
without the 30M-row bulk dump. Golden test (test_golden_recall) is marked
``rf_ingested`` and skipped unless the real RF data is loaded.
"""

import csv
from pathlib import Path

import pytest
from sqlalchemy import text

from agente10.empresas.discovery import EmpresaCandidate, find_empresas_by_cnae

pytestmark = pytest.mark.integration

SYNTHETIC_SQL = Path(__file__).parent.parent / "fixtures" / "cnpj_synthetic.sql"
GOLDEN_CSV = Path(__file__).parent.parent / "fixtures" / "empresas_golden.csv"
MIN_RECALL_AT_25 = 0.80


async def _load_synthetic(db_session) -> None:
    """Apply the synthetic fixture inside the current transaction."""
    sql = SYNTHETIC_SQL.read_text(encoding="utf-8")
    for statement in sql.split(";"):
        s = statement.strip()
        if s and not s.startswith("--"):
            await db_session.execute(text(s))


# --- Shape tests (synthetic fixture, no RF dump) -----------------------------


@pytest.mark.asyncio
async def test_returns_typed_candidates(db_session):
    await _load_synthetic(db_session)
    candidates = await find_empresas_by_cnae(db_session, "9991001", limit=10)
    assert len(candidates) > 0
    assert all(isinstance(c, EmpresaCandidate) for c in candidates)
    assert all(len(c.cnpj) == 14 for c in candidates)
    assert all(c.razao_social for c in candidates)


@pytest.mark.asyncio
async def test_primary_matches_come_before_secondary(db_session):
    await _load_synthetic(db_session)
    candidates = await find_empresas_by_cnae(db_session, "9991001", limit=25)
    flags = [c.primary_match for c in candidates]
    # All True flags must precede the first False flag
    assert flags == sorted(flags, reverse=True)


@pytest.mark.asyncio
async def test_uf_filter_excludes_others(db_session):
    await _load_synthetic(db_session)
    candidates = await find_empresas_by_cnae(db_session, "9991001", uf="SP", limit=25)
    assert all(c.uf == "SP" for c in candidates)


@pytest.mark.asyncio
async def test_secondary_only_match_returns_via_array(db_session):
    await _load_synthetic(db_session)
    # Row 62 has cnae_primario='4684201'; 4744001 appears only in its cnaes_secundarios.
    # Querying for 4744001 should still return row 62, with primary_match=False.
    candidates = await find_empresas_by_cnae(db_session, "9991001", limit=25)
    # Row 62 has 4744001 in secondaries only; should appear with primary_match=False
    cnpjs = {c.cnpj: c for c in candidates}
    assert "00000062000101" in cnpjs
    assert cnpjs["00000062000101"].primary_match is False


@pytest.mark.asyncio
async def test_respects_limit(db_session):
    await _load_synthetic(db_session)
    for k in (1, 3, 10):
        candidates = await find_empresas_by_cnae(db_session, "9991001", limit=k)
        assert len(candidates) <= k


# --- Golden test (requires bulk RF data) -------------------------------------


@pytest.mark.rf_ingested
@pytest.mark.asyncio
async def test_golden_recall_at_25(db_session):
    """Known-CNPJ recall@25 against the real RF dump."""
    with GOLDEN_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 10

    misses: list[tuple[str, str, list[str]]] = []
    for r in rows:
        candidates = await find_empresas_by_cnae(
            db_session, r["cnae"], uf=r.get("uf") or None, limit=25
        )
        cnpjs = [c.cnpj for c in candidates]
        if r["cnpj_esperado"] not in cnpjs:
            misses.append((r["descricao"], r["cnpj_esperado"], cnpjs[:5]))

    recall = 1 - len(misses) / len(rows)
    if misses:
        report = "\n".join(f"  - {d}: esperado {e}, top-5 = {c}" for d, e, c in misses)
        print(f"\nMisses ({len(misses)}/{len(rows)}):\n{report}")
    assert recall >= MIN_RECALL_AT_25, f"recall@25 = {recall:.2f}, esperado >= {MIN_RECALL_AT_25}"
