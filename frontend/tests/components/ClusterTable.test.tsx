// frontend/tests/components/ClusterTable.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ClusterTable } from "../../components/cluster/ClusterTable";
import type { ClusterSummary } from "../../lib/types";

const sample: ClusterSummary[] = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    nome_cluster: "Parafusos",
    nome_cluster_refinado: null,
    cnae: "4744001",
    cnae_descricao: "Ferragens",
    cnae_confianca: 0.92,
    cnae_metodo: "retrieval",
    cnaes_secundarios: [],
    num_linhas: 6,
    revisado_humano: false,
    shortlist_size: 10,
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    nome_cluster: "Geradores",
    nome_cluster_refinado: null,
    cnae: null,
    cnae_descricao: null,
    cnae_confianca: null,
    cnae_metodo: null,
    cnaes_secundarios: [],
    num_linhas: 4,
    revisado_humano: true,
    shortlist_size: 0,
  },
];

describe("ClusterTable", () => {
  it("renders all rows when search is empty", () => {
    render(<ClusterTable clusters={sample} searchTerm="" />);
    expect(screen.getByText("Parafusos")).toBeInTheDocument();
    expect(screen.getByText("Geradores")).toBeInTheDocument();
  });

  it("filters by searchTerm", () => {
    render(<ClusterTable clusters={sample} searchTerm="paraf" />);
    expect(screen.getByText("Parafusos")).toBeInTheDocument();
    expect(screen.queryByText("Geradores")).not.toBeInTheDocument();
  });

  it("shows empty state when no match", () => {
    render(<ClusterTable clusters={sample} searchTerm="xyz" />);
    expect(screen.getByText(/Nenhum cluster/)).toBeInTheDocument();
  });
});
