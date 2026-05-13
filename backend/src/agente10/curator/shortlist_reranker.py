"""LLM curator: rerank find_empresas_by_cnae candidates → top-10."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from agente10.curator.client import CuratorClient
from agente10.empresas.discovery import EmpresaCandidate

_SYSTEM = """\
Você é um especialista em supply chain B2B Brasil. Dado o nome de uma
categoria de materiais/serviços e até 25 fornecedores candidatos
(razão social, capital social, UF, idade), retorne os 10 melhores em
ordem decrescente de relevância como JSON puro:

[
  {"cnpj": "<14 digitos>", "rank": <1-10>, "reasoning": "<breve>"},
  ...
]

Regras:
- Exatamente 10 itens (ou menos se input tem <10).
- Cada cnpj DEVE estar entre os candidatos.
- Priorize fornecedores claramente especializados na categoria, com
  capital social compatível com o ticket esperado.
"""


class RankedSupplier(BaseModel):
    cnpj: str
    rank: int
    reasoning: str


def _format_user_prompt(cluster_name: str, candidates: list[EmpresaCandidate]) -> str:
    today = date.today()
    lines = [f"Categoria: {cluster_name}", "", "Candidatos:"]
    for i, c in enumerate(candidates, start=1):
        idade = (today - c.data_abertura).days // 365 if c.data_abertura else "N/A"
        lines.append(f"{i}. {c.cnpj} — {c.razao_social} | UF={c.uf} | idade={idade}a")
    return "\n".join(lines)


async def rerank_top10(
    client: CuratorClient,
    cluster_name: str,
    candidates: list[EmpresaCandidate],
) -> list[RankedSupplier]:
    """Ask curator to rerank to top-10. Returns sorted by rank ascending."""
    user = _format_user_prompt(cluster_name, candidates)
    raw = await client.ask_json(_SYSTEM, user, max_tokens=2048)
    ranked = [RankedSupplier.model_validate(item) for item in raw]
    valid_cnpjs = {c.cnpj for c in candidates}
    bad = [r.cnpj for r in ranked if r.cnpj not in valid_cnpjs]
    if bad:
        raise ValueError(f"reranker returned cnpjs not in input candidates: {bad}")
    return sorted(ranked, key=lambda r: r.rank)
