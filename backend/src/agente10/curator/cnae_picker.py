"""LLM curator: pick the best CNAE for a cluster name from top-K retrieval candidates."""

from __future__ import annotations

from pydantic import BaseModel

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.client import CuratorClient

_SYSTEM = """\
Você é um classificador especialista em CNAE 2.3 brasileira. Dado o nome
de uma categoria de materiais/serviços e até 5 candidatos CNAE, escolha
o mais apropriado e retorne JSON puro no formato:

{"cnae": "<codigo 7 digitos>", "confidence": <0.0-1.0>, "reasoning": "<breve>"}

Regras:
- O cnae escolhido DEVE estar entre os candidatos fornecidos.
- confidence reflete o quanto você está seguro (0.5 = chute educado, 0.9 = óbvio).
- reasoning em 1-2 frases.
"""


class CnaePick(BaseModel):
    """LLM choice over top-K CNAE candidates."""

    cnae: str
    confidence: float
    reasoning: str


def _format_user_prompt(cluster_name: str, candidates: list[CnaeCandidate]) -> str:
    lines = [f"Categoria: {cluster_name}", "", "Candidatos CNAE:"]
    for i, c in enumerate(candidates, start=1):
        lines.append(f"{i}. {c.codigo} — {c.denominacao} (sim={c.similarity:.3f})")
    return "\n".join(lines)


async def pick_cnae(
    client: CuratorClient,
    cluster_name: str,
    candidates: list[CnaeCandidate],
) -> CnaePick:
    """Ask the curator to pick the best CNAE from the candidates."""
    user = _format_user_prompt(cluster_name, candidates)
    raw = await client.ask_json(_SYSTEM, user)
    pick = CnaePick.model_validate(raw)
    valid_codes = {c.codigo for c in candidates}
    if pick.cnae not in valid_codes:
        raise ValueError(f"curator returned cnae {pick.cnae!r} not in candidates {valid_codes}")
    return pick
