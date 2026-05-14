"""LLM curator: pick the best CNAE(s) for a cluster name from top-K retrieval candidates.

Supports:
- Adaptive truncation: when top-K similarities are tight (<0.05 spread), expand
  notas/exemplos to give the LLM more context.
- Hierarchy context: passes Divisão/Grupo intro descriptions, helping when the
  subclass denominação is ambiguous on its own.
- Few-shot examples from cache (revisado_humano + golden seeds).
- Multi-CNAE: optionally returns up to N secondary CNAEs the LLM considers also
  relevant — useful when the cluster's spend mixes multiple activities.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agente10.cache.classification_cache import FewShotExample
from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.client import CuratorClient

_SYSTEM = """\
Você é um classificador especialista em CNAE 2.3 brasileira. Dado o nome de
uma categoria de materiais/serviços e até 5 candidatos CNAE com suas notas
explicativas do IBGE, escolha o CNAE primário (o mais representativo) e até
2 secundários (apenas se a categoria genuinamente cobre múltiplas atividades).

Retorne JSON puro:

{
  "cnae": "<codigo 7 digitos>",
  "confidence": <0.0-1.0>,
  "secondary_cnaes": ["<codigo>", ...],
  "reasoning": "<breve, max 2 frases>"
}

Regras:
- Todos os códigos retornados DEVEM estar entre os candidatos fornecidos.
- secondary_cnaes pode ser [] (lista vazia) — só preencha se houver mais de
  uma atividade econômica claramente diferente coberta pelo cluster.
- confidence reflete o quanto está seguro do PRIMÁRIO (0.5 chute, 0.9 óbvio).
- Use "Compreende" / "NÃO compreende" para desambiguar irmãs.
- Use a Divisão/Grupo do candidato como pista de domínio macro.
- Se exemplos validados forem fornecidos, eles têm prioridade alta.
"""


class CnaePick(BaseModel):
    """LLM choice over top-K CNAE candidates (primary + optional secondaries)."""

    cnae: str
    confidence: float
    reasoning: str
    secondary_cnaes: list[str] = Field(default_factory=list)


# Default truncation lengths — used when top-K candidates are well-separated.
_DENOM_TRUNC_DEFAULT = 250
_EXEMPLOS_TRUNC_DEFAULT = 250
_NOTAS_TRUNC_DEFAULT = 350
# Expanded truncation when top-K is tight (curator needs more context to disambiguate).
_EXEMPLOS_TRUNC_TIGHT = 500
_NOTAS_TRUNC_TIGHT = 700
# Hierarchy descriptions can be long — keep them on the lean side.
_DIVISAO_TRUNC = 280
_GRUPO_TRUNC = 220


def _is_tight(candidates: list[CnaeCandidate]) -> bool:
    """True when top candidates are within 0.05 cosine of each other (hard to disambiguate)."""
    if len(candidates) < 2:
        return False
    return (candidates[0].similarity - candidates[1].similarity) < 0.05


def _format_user_prompt(
    cluster_name: str,
    candidates: list[CnaeCandidate],
    few_shots: list[FewShotExample] | None = None,
    sample_lines: list[str] | None = None,
) -> str:
    tight = _is_tight(candidates)
    ex_trunc = _EXEMPLOS_TRUNC_TIGHT if tight else _EXEMPLOS_TRUNC_DEFAULT
    no_trunc = _NOTAS_TRUNC_TIGHT if tight else _NOTAS_TRUNC_DEFAULT

    lines: list[str] = []

    if few_shots:
        lines.append("Exemplos de classificações já validadas (use como referência):")
        for ex in few_shots:
            tag = "[humano]" if ex.metodo == "revisado_humano" else "[golden]"
            lines.append(f'  - "{ex.descricao}" → {ex.cnae} {tag}')
        lines.append("")

    lines.append(f"Categoria: {cluster_name}")
    if sample_lines:
        lines.append("Exemplos de linhas no cluster:")
        for s in sample_lines[:5]:
            lines.append(f"  - {s[:120]}")
    if tight:
        lines.append("(top candidatos muito próximos em similaridade — leia atentamente)")
    lines.append("")
    lines.append("Candidatos CNAE:")

    seen_div: set[str] = set()
    seen_grp: set[str] = set()
    for i, c in enumerate(candidates, start=1):
        denom_short = c.denominacao[:_DENOM_TRUNC_DEFAULT]
        lines.append(f"{i}. {c.codigo} — {denom_short} (sim={c.similarity:.3f})")
        # Divisão context shown once per division to control token cost
        if c.divisao_descricao:
            div_key = c.divisao_descricao[:60]
            if div_key not in seen_div:
                seen_div.add(div_key)
                div_txt = c.divisao_descricao.replace("\n", " ").strip()
                lines.append(f"   Divisão: {div_txt[:_DIVISAO_TRUNC]}")
        if c.grupo_descricao:
            grp_key = c.grupo_descricao[:60]
            if grp_key not in seen_grp:
                seen_grp.add(grp_key)
                grp_txt = c.grupo_descricao.replace("\n", " ").strip()
                lines.append(f"   Grupo: {grp_txt[:_GRUPO_TRUNC]}")
        if c.exemplos_atividades:
            ex_txt = c.exemplos_atividades.replace("\n", " ").strip()
            lines.append(f"   Compreende: {ex_txt[:ex_trunc]}")
        if c.notas_explicativas:
            no_txt = c.notas_explicativas.replace("\n", " ").strip()
            lines.append(f"   NÃO compreende: {no_txt[:no_trunc]}")

    return "\n".join(lines)


async def pick_cnae(
    client: CuratorClient,
    cluster_name: str,
    candidates: list[CnaeCandidate],
    few_shots: list[FewShotExample] | None = None,
    sample_lines: list[str] | None = None,
) -> CnaePick:
    """Ask the curator to pick the best CNAE (+ optional secondaries) from candidates."""
    user = _format_user_prompt(cluster_name, candidates, few_shots, sample_lines)
    raw = await client.ask_json(_SYSTEM, user)
    pick = CnaePick.model_validate(raw)
    valid_codes = {c.codigo for c in candidates}
    if pick.cnae not in valid_codes:
        raise ValueError(f"curator returned cnae {pick.cnae!r} not in candidates {valid_codes}")
    # Filter secondaries to valid candidate codes (LLM can hallucinate); also drop
    # the primary if it shows up there.
    pick.secondary_cnaes = [c for c in pick.secondary_cnaes if c in valid_codes and c != pick.cnae][
        :2
    ]
    return pick
