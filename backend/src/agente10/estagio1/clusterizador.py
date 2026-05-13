"""Hybrid clustering: trust client's `agrupamento` field; HDBSCAN on the rest.

Output: one ClusterAssignment per input row. Cluster names come from
agrupamento (lowercased/trimmed) or top-3 TF-IDF terms for embedding clusters.
"""

from __future__ import annotations

from collections.abc import Sequence

import hdbscan
import numpy as np
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer

from agente10.estagio1.csv_parser import ParsedRow
from agente10.integrations.voyage import VoyageClient


class ClusterAssignment(BaseModel):
    """One row → its cluster name (or 'unassigned' if clustering failed)."""

    row_index: int
    cluster_name: str


def _agrupamento_clusters(rows: Sequence[ParsedRow]) -> tuple[list[ClusterAssignment], list[int]]:
    """Return assignments for rows with agrupamento + indices of rows without."""
    assigned: list[ClusterAssignment] = []
    no_agrup: list[int] = []
    for i, row in enumerate(rows):
        if row.agrupamento and row.agrupamento.strip():
            assigned.append(
                ClusterAssignment(row_index=i, cluster_name=row.agrupamento.strip().lower())
            )
        else:
            no_agrup.append(i)
    return assigned, no_agrup


def _tfidf_label(texts: Sequence[str], top_n: int = 3) -> str:
    """Pick the top-N TF-IDF terms across a cluster's descriptions, joined."""
    if not texts:
        return "unnamed"
    if len(texts) == 1:
        return texts[0].strip().lower()[:60]
    vec = TfidfVectorizer(max_features=200, ngram_range=(1, 1), lowercase=True)
    matrix = vec.fit_transform(texts)
    scores = matrix.sum(axis=0).A1
    terms = vec.get_feature_names_out()
    top_idx = scores.argsort()[::-1][:top_n]
    return " ".join(terms[i] for i in top_idx)


async def _embedding_clusters(
    rows: Sequence[ParsedRow],
    indices: Sequence[int],
    voyage: VoyageClient,
    min_cluster_size: int,
) -> list[ClusterAssignment]:
    if not indices:
        return []
    texts = [rows[i].descricao_original for i in indices]
    embeddings = await voyage.embed_documents(texts)
    matrix = np.asarray(embeddings, dtype=np.float64)

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)  # avoid div-by-zero
    normalized = matrix / norms

    n_samples = len(indices)
    eff_min = max(min_cluster_size, 2)

    # HDBSCAN needs at least min_cluster_size samples; fall back to singletons for tiny inputs.
    if n_samples < eff_min:
        out: list[ClusterAssignment] = []
        if n_samples == 1:
            row_idx = indices[0]
            out.append(
                ClusterAssignment(
                    row_index=row_idx,
                    cluster_name=rows[row_idx].descricao_original.strip().lower()[:60],
                )
            )
        else:
            name = _tfidf_label([rows[i].descricao_original for i in indices])
            for row_idx in indices:
                out.append(ClusterAssignment(row_index=row_idx, cluster_name=name))
        return out

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=eff_min,
        metric="euclidean",  # cosine via pre-normalized vectors
        algorithm="generic",  # avoids kdtree k-neighbour constraint on small datasets
        allow_single_cluster=True,  # avoid all-noise when data is tight / few samples
    )
    labels = clusterer.fit_predict(normalized)

    # Group row indices by cluster label
    label_to_indices: dict[int, list[int]] = {}
    for local_idx, label in enumerate(labels):
        label_to_indices.setdefault(int(label), []).append(local_idx)

    out: list[ClusterAssignment] = []
    for label, local_indices in label_to_indices.items():
        if label == -1:
            # Noise → each row becomes its own singleton cluster
            for li in local_indices:
                row_idx = indices[li]
                out.append(
                    ClusterAssignment(
                        row_index=row_idx,
                        cluster_name=rows[row_idx].descricao_original.strip().lower()[:60],
                    )
                )
        else:
            texts_for_label = [rows[indices[li]].descricao_original for li in local_indices]
            name = _tfidf_label(texts_for_label)
            for li in local_indices:
                out.append(ClusterAssignment(row_index=indices[li], cluster_name=name))
    return out


async def cluster_rows(
    rows: Sequence[ParsedRow],
    voyage: VoyageClient,
    min_cluster_size: int = 3,
) -> list[ClusterAssignment]:
    """Hybrid: agrupamento path + HDBSCAN embedding path. Returns 1 assignment per row."""
    assigned, no_agrup = _agrupamento_clusters(rows)
    embedded = await _embedding_clusters(rows, no_agrup, voyage, min_cluster_size)
    return sorted(assigned + embedded, key=lambda a: a.row_index)
