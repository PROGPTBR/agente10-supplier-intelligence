"""Parse client catalog CSV/XLSX into Pydantic ParsedRow objects.

Required column: descricao_original.
Optional columns map 1:1 to spend_linhas fields; unknown columns → extras JSONB.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import Any

import chardet
from openpyxl import load_workbook
from pydantic import BaseModel


class CsvParseError(ValueError):
    """Raised when the catalog file is malformed."""


_KNOWN_COLUMNS = {
    "descricao_original",
    "agrupamento",
    "id_linha_origem",
    "fornecedor_atual",
    "cnpj_fornecedor",
    "valor_total",
    "quantidade",
    "uf_solicitante",
    "municipio_solicitante",
    "centro_custo",
    "data_compra",
}


class ParsedRow(BaseModel):
    """One line of the client catalog, ready to insert into spend_linhas."""

    descricao_original: str
    agrupamento: str | None = None
    id_linha_origem: str | None = None
    fornecedor_atual: str | None = None
    cnpj_fornecedor: str | None = None
    valor_total: str | None = None
    quantidade: str | None = None
    uf_solicitante: str | None = None
    municipio_solicitante: str | None = None
    centro_custo: str | None = None
    data_compra: str | None = None
    extras: dict[str, Any] = {}


def _decode(raw: bytes) -> str:
    """Decode bytes using chardet to detect encoding (cp1252/utf-8 mostly)."""
    detection = chardet.detect(raw)
    encoding = detection.get("encoding") or "utf-8"
    try:
        return raw.decode(encoding)
    except (UnicodeDecodeError, LookupError) as exc:
        raise CsvParseError(f"unable to decode file (detected {encoding!r}): {exc}") from exc


def _is_xlsx(filename: str) -> bool:
    return filename.lower().endswith((".xlsx", ".xlsm"))


def _row_from_dict(line_num: int, raw: dict[str, str]) -> ParsedRow:
    descricao = (raw.get("descricao_original") or "").strip()
    if not descricao:
        raise CsvParseError(f"empty descricao_original at line {line_num}")
    extras = {k: v for k, v in raw.items() if k and k not in _KNOWN_COLUMNS and v}
    known = {
        k: (v.strip() if isinstance(v, str) else v) or None
        for k, v in raw.items()
        if k in _KNOWN_COLUMNS
    }
    known["descricao_original"] = descricao  # already trimmed
    return ParsedRow(**known, extras=extras)


def _parse_csv_text(text: str) -> Iterator[ParsedRow]:
    raw_reader = csv.reader(io.StringIO(text))
    header_row = next(raw_reader, None)
    if not header_row or "descricao_original" not in header_row:
        raise CsvParseError("missing required column 'descricao_original'")
    headers = header_row
    for i, values in enumerate(raw_reader, start=2):  # line 1 = header
        # csv.reader still skips truly empty lines; reconstruct blank row to trigger validation
        if not values:
            raw: dict[str, str] = {"descricao_original": ""}
        else:
            raw = dict(zip(headers, values, strict=False))
        yield _row_from_dict(i, raw)


def _parse_xlsx(data: bytes) -> Iterator[ParsedRow]:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    headers = next(rows, None)
    if not headers or "descricao_original" not in headers:
        raise CsvParseError("missing required column 'descricao_original'")
    headers = [str(h) if h is not None else "" for h in headers]
    for i, values in enumerate(rows, start=2):
        raw = {h: ("" if v is None else str(v)) for h, v in zip(headers, values, strict=False)}
        yield _row_from_dict(i, raw)


def parse_catalog_bytes(data: bytes, filename: str) -> Iterator[ParsedRow]:
    """Yield ParsedRow objects from a CSV or XLSX file's raw bytes."""
    if _is_xlsx(filename):
        yield from _parse_xlsx(data)
    else:
        yield from _parse_csv_text(_decode(data))
