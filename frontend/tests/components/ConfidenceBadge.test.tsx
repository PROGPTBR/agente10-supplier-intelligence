// frontend/tests/components/ConfidenceBadge.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfidenceBadge } from "../../components/cluster/ConfidenceBadge";

describe("ConfidenceBadge", () => {
  it("renders 'Auto' for retrieval", () => {
    render(<ConfidenceBadge metodo="retrieval" confianca={0.92} />);
    expect(screen.getByText("Auto")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
  });

  it("renders 'Manual' for manual_pending", () => {
    render(<ConfidenceBadge metodo="manual_pending" confianca={0.5} />);
    expect(screen.getByText("Manual")).toBeInTheDocument();
  });

  it("renders dash when metodo is null", () => {
    render(<ConfidenceBadge metodo={null} confianca={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
