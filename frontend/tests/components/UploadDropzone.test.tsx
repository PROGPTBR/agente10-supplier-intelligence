import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { UploadDropzone } from "../../components/upload/UploadDropzone";

function makeFile(name: string, size = 100): File {
  const file = new File([new Uint8Array(size)], name, { type: "text/csv" });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("UploadDropzone", () => {
  it("accepts CSV and fires onFile", () => {
    const onFile = vi.fn();
    render(<UploadDropzone onFile={onFile} />);
    const input = screen.getByLabelText(
      "Arquivo de catálogo",
    ) as HTMLInputElement;
    const file = makeFile("a.csv");
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("rejects non-CSV files", () => {
    const onFile = vi.fn();
    render(<UploadDropzone onFile={onFile} />);
    const input = screen.getByLabelText(
      "Arquivo de catálogo",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("a.pdf")] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByText(/Formato inválido/)).toBeInTheDocument();
  });

  it("rejects files larger than 50MB", () => {
    const onFile = vi.fn();
    render(<UploadDropzone onFile={onFile} />);
    const input = screen.getByLabelText(
      "Arquivo de catálogo",
    ) as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [makeFile("a.csv", 51 * 1024 * 1024)] },
    });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByText(/muito grande/)).toBeInTheDocument();
  });
});
