"""Auto-suggestion of trade-tier sibling CNAEs (fabricação / atacado / varejo).

When the classifier picks a CNAE for a cluster, this module finds the related
codes in the other commerce tiers using `embedding_rich` cosine similarity,
scoped by IBGE division ranges. Used so the shortlist also pulls suppliers
that are wholesale distributors or retailers of the same product family, not
only manufacturers (or vice-versa).

Rules:
- Divisões 10-33 (Seção C) → fabricação
- Divisão 46              → atacado
- Divisão 47              → varejo
- Outras divisões → no tier (function returns None, caller skips suggestion)

Normalization preference: if a fabricação sibling exists for a primary in
atacado/varejo, swap so fabricação becomes primary. ELETROBRÁS-style B2B
sourcing usually wants manufacturers + their authorised distributors, not
retail-only suppliers.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Tier = Literal["fabricacao", "atacado", "varejo"]

DEFAULT_THRESHOLD = 0.65
MAX_SECONDARIES = 4

_TIER_DIVISION_RANGE: dict[Tier, tuple[int, int]] = {
    "fabricacao": (10, 33),
    "atacado": (46, 46),
    "varejo": (47, 47),
}


def _tier_for(codigo: str) -> Tier | None:
    """Map a 7-digit CNAE code to its trade tier, or None if outside C/46/47."""
    if not codigo or len(codigo) < 2 or not codigo[:2].isdigit():
        return None
    div = int(codigo[:2])
    if 10 <= div <= 33:
        return "fabricacao"
    if div == 46:
        return "atacado"
    if div == 47:
        return "varejo"
    return None


async def find_trade_tier_siblings(
    db: AsyncSession,
    primary_cnae: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[Tier, str | None]:
    """For a primary CNAE in one of the three tiers, find the best sibling in
    each of the other two tiers via embedding_rich cosine similarity.

    Returns a dict keyed by tier; the primary's own tier echoes back its own
    code. Tiers that don't have a sibling above `threshold` map to None.
    A primary CNAE outside divisions 10-33/46/47 returns {} (caller should
    skip the auto-suggestion entirely).
    """
    primary_tier = _tier_for(primary_cnae)
    if primary_tier is None:
        return {}

    emb_row = (
        await db.execute(
            text(
                "SELECT embedding_rich::text AS emb "
                "FROM cnae_taxonomy WHERE codigo = :c AND embedding_rich IS NOT NULL"
            ),
            {"c": primary_cnae},
        )
    ).first()
    if emb_row is None:
        # Primary CNAE has no rich embedding yet — can't look up siblings.
        return {primary_tier: primary_cnae}

    primary_emb = emb_row.emb

    out: dict[Tier, str | None] = {primary_tier: primary_cnae}
    for tier, (dmin, dmax) in _TIER_DIVISION_RANGE.items():
        if tier == primary_tier:
            continue
        row = (
            await db.execute(
                text(
                    "SELECT codigo, "
                    "       1 - (embedding_rich <=> CAST(:emb AS vector)) AS sim "
                    "FROM cnae_taxonomy "
                    "WHERE CAST(divisao AS int) BETWEEN :dmin AND :dmax "
                    "  AND embedding_rich IS NOT NULL "
                    "  AND codigo <> :p "
                    "ORDER BY embedding_rich <=> CAST(:emb AS vector) "
                    "LIMIT 1"
                ),
                {
                    "emb": primary_emb,
                    "dmin": dmin,
                    "dmax": dmax,
                    "p": primary_cnae,
                },
            )
        ).first()
        if row is not None and float(row.sim) >= threshold:
            out[tier] = row.codigo
        else:
            out[tier] = None
    return out


def normalize_to_fabricacao_first(
    primary: str,
    secondaries: list[str],
    siblings: dict[Tier, str | None],
) -> tuple[str, list[str]]:
    """Combine the classifier's primary + curator-supplied secondaries with the
    trade-tier siblings, preferring fabricação as the primary when available.

    - If `siblings == {}` (primary is outside C/46/47), returns inputs unchanged
      so service/consultoria clusters are not touched.
    - Curator secondaries are preserved.
    - When a fabricação sibling exists and the primary isn't already fabricação,
      the fabricação code becomes primary and the original primary is demoted
      to the secondary list.
    - Dedups and caps the secondary list at MAX_SECONDARIES.
    """
    if not siblings:
        return primary, list(secondaries)

    fab = siblings.get("fabricacao")
    atac = siblings.get("atacado")
    var = siblings.get("varejo")

    if fab is not None and fab != primary:
        new_primary = fab
        # Original primary is demoted ahead of curator picks so the relationship
        # is preserved if the secondary cap evicts older entries.
        ordered = [primary]
        if atac and atac != fab and atac != primary:
            ordered.append(atac)
        if var and var != fab and var != primary:
            ordered.append(var)
        ordered.extend(secondaries)
    else:
        new_primary = primary
        ordered = list(secondaries)
        for sibling in (fab, atac, var):
            if sibling is None:
                continue
            if sibling == new_primary:
                continue
            ordered.append(sibling)

    seen: set[str] = set()
    deduped: list[str] = []
    for code in ordered:
        if code == new_primary or code in seen:
            continue
        seen.add(code)
        deduped.append(code)
        if len(deduped) >= MAX_SECONDARIES:
            break
    return new_primary, deduped
