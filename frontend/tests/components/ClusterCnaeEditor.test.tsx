import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ClusterCnaeEditor } from "../../components/cluster/ClusterCnaeEditor";

describe("ClusterCnaeEditor", () => {
  it("filters by user input", () => {
    const onChange = vi.fn();
    render(<ClusterCnaeEditor value={null} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Pesquisar CNAE"), {
      target: { value: "0600001" },
    });
    expect(screen.getByText("0600001")).toBeInTheDocument();
  });

  it("fires onChange when clicking an option", () => {
    const onChange = vi.fn();
    render(<ClusterCnaeEditor value={null} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Pesquisar CNAE"), {
      target: { value: "0600001" },
    });
    fireEvent.click(screen.getByText("0600001"));
    expect(onChange).toHaveBeenCalledWith("0600001");
  });
});
