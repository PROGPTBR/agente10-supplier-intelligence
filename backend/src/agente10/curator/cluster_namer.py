"""LLM helper that produces a broader, CNAE-connected name for a spend cluster.

The clusterizer's `nome_cluster` is the centroid representative description —
often too specific ("Locação Motoniveladora") or hyper-narrow when the cluster
has 1-2 lines. After CNAE is assigned, this refiner generates a 3-6 word name
that is wide enough to cover the cluster's lines and aligned with the CNAE's
domain (e.g., "Aluguel de máquinas para terraplanagem").
"""

from __future__ import annotations

from pydantic import BaseModel

from agente10.curator.client import CuratorClient

_SYSTEM = """\
Você é um especialista em categorização de demanda corporativa. Dado:
1. o nome bruto de um cluster de itens de catálogo,
2. até 5 descrições de itens reais do cluster,
3. o CNAE primário atribuído + denominação,
produza um NOVO nome para o cluster que:
- Seja conciso (3-6 palavras) em português brasileiro.
- Generalize o tipo de demanda (cubra TODOS os itens do cluster, não só um).
- Esteja conectado ao DOMÍNIO do CNAE (mesma família de atividade).
- NÃO inclua marcas, números de modelo, ou capacidades específicas.
- Use letra maiúscula só no início (Title Case suave).

Retorne JSON puro:
{"nome": "<novo nome>", "rationale": "<1 frase>"}
"""


class RefinedClusterName(BaseModel):
    nome: str
    rationale: str = ""


async def refine_cluster_name(
    client: CuratorClient,
    nome_atual: str,
    sample_lines: list[str],
    cnae_codigo: str,
    cnae_denominacao: str,
) -> RefinedClusterName:
    user_lines = [
        f"Nome atual: {nome_atual}",
        f"CNAE atribuído: {cnae_codigo} — {cnae_denominacao}",
        "Itens do cluster:",
    ]
    for s in sample_lines[:5]:
        user_lines.append(f"  - {s[:120]}")
    raw = await client.ask_json(_SYSTEM, "\n".join(user_lines))
    out = RefinedClusterName.model_validate(raw)
    # Safety: cap length and strip whitespace
    out.nome = out.nome.strip()[:120]
    return out
