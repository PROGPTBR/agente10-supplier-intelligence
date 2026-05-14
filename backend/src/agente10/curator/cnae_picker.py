"""LLM curator: pick the best CNAE for a cluster name from top-K retrieval candidates."""

from __future__ import annotations

from pydantic import BaseModel

from agente10.cache.classification_cache import FewShotExample
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
- Use as notas IBGE ("Compreende" / "NÃO compreende") para desambiguar irmãs.
- Se exemplos validados forem fornecidos, use-os como referência prioritária.
"""


class CnaePick(BaseModel):
    """LLM choice over top-K CNAE candidates."""

    cnae: str
    confidence: float
    reasoning: str


_NOTES_TRUNCATE = 350
_EXEMPLOS_TRUNCATE = 250


def _format_user_prompt(
    cluster_name: str,
    candidates: list[CnaeCandidate],
    few_shots: list[FewShotExample] | None = None,
) -> str:
    lines: list[str] = []
    if few_shots:
        lines.append("Exemplos de classificações já validadas (use como referência):")
        for ex in few_shots:
            tag = "[humano]" if ex.metodo == "revisado_humano" else "[golden]"
            lines.append(f'  - "{ex.descricao}" → {ex.cnae} {tag}')
        lines.append("")
    lines.append(f"Categoria: {cluster_name}")
    lines.append("")
    lines.append("Candidatos CNAE:")
    for i, c in enumerate(candidates, start=1):
        lines.append(f"{i}. {c.codigo} — {c.denominacao} (sim={c.similarity:.3f})")
        # IBGE notas/exemplos disambiguate sibling subclasses; truncate to keep
        # prompt cost bounded (~700 tokens extra per 5-candidate call on Haiku).
        if c.exemplos_atividades:
            ex_txt = c.exemplos_atividades.replace("\n", " ").strip()
            lines.append(f"   Compreende: {ex_txt[:_EXEMPLOS_TRUNCATE]}")
        if c.notas_explicativas:
            no = c.notas_explicativas.replace("\n", " ").strip()
            lines.append(f"   NÃO compreende: {no[:_NOTES_TRUNCATE]}")
    return "\n".join(lines)


async def pick_cnae(
    client: CuratorClient,
    cluster_name: str,
    candidates: list[CnaeCandidate],
    few_shots: list[FewShotExample] | None = None,
) -> CnaePick:
    """Ask the curator to pick the best CNAE from the candidates."""
    user = _format_user_prompt(cluster_name, candidates, few_shots)
    raw = await client.ask_json(_SYSTEM, user)
    pick = CnaePick.model_validate(raw)
    valid_codes = {c.codigo for c in candidates}
    if pick.cnae not in valid_codes:
        raise ValueError(f"curator returned cnae {pick.cnae!r} not in candidates {valid_codes}")
    return pick
