"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

const MAX_BYTES = 50 * 1024 * 1024;
const ACCEPTED = [".csv", ".xlsx", ".xlsm"];

export interface UploadDropzoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
}

function validate(file: File): string | null {
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
  if (!ACCEPTED.includes(ext)) return "Formato inválido — use CSV ou XLSX";
  if (file.size > MAX_BYTES) return "Arquivo muito grande (>50MB)";
  return null;
}

export function UploadDropzone({ onFile, disabled }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFile(file: File) {
    const err = validate(file);
    if (err) {
      setError(err);
      return;
    }
    setError(null);
    onFile(file);
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setHover(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setHover(true);
        }}
        onDragLeave={() => setHover(false)}
        onDrop={onDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        className={`flex h-48 cursor-pointer items-center justify-center rounded-lg border-2 border-dashed text-center transition ${
          hover
            ? "border-emerald-500 bg-emerald-50"
            : "border-zinc-300 bg-zinc-50"
        } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
      >
        <div>
          <p className="text-sm font-medium text-zinc-700">
            Arraste seu CSV ou XLSX aqui
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            ou clique para selecionar — máx 50MB · coluna{" "}
            <code>descricao_original</code> obrigatória
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          className="hidden"
          onChange={onChange}
          aria-label="Arquivo de catálogo"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
