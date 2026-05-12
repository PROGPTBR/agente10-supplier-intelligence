"""Parse the IBGE CNAE 2.3 "Estrutura Detalhada" XLSX into taxonomy.json.

Usage:
    cd backend && uv run python scripts/parse_ibge_xls.py

Reads:  data/cnae_2.3/raw/CNAE_2.3_Estrutura_Detalhada.xlsx
Writes: data/cnae_2.3/taxonomy.json (1331 entries; raises if count differs)

The IBGE XLSX uses merged cells for Seção / Divisão / Grupo / Classe so we forward-fill
those columns. Subclass rows are detected by a 7-digit-ish code pattern; the description
columns immediately below a subclass row contain the "Esta subclasse compreende:" /
"compreende também:" / "não compreende:" notes (multi-line).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

RAW_PATH = (
    Path(__file__).parent.parent / "data" / "cnae_2.3" / "raw"
    / "CNAE_2.3_Estrutura_Detalhada.xlsx"
)
OUT_PATH = Path(__file__).parent.parent / "data" / "cnae_2.3" / "taxonomy.json"
EXPECTED_COUNT = 1331

# IBGE subclass codes are 7-digit strings; XLSX often shows them as "XXXX-X/XX" or "XX.XX-X-XX".
# We normalize to 7 digits only.
SUBCLASS_RE = re.compile(r"^\s*(\d{2})[\.\-]?(\d{2})[\-\.]?(\d)[\-\./]?(\d{2})\s*$")
DIVISAO_RE = re.compile(r"^\s*(\d{2})\s*$")
GRUPO_RE = re.compile(r"^\s*(\d{2})[\.\-](\d)\s*$")
CLASSE_RE = re.compile(r"^\s*(\d{2})[\.\-](\d{2})[\-](\d)\s*$")
SECAO_RE = re.compile(r"^\s*([A-U])\s*$")


def _norm_code(raw: str) -> str | None:
    """Normalize a subclass cell to its 7-digit code, or return None if not a subclass."""
    if raw is None:
        return None
    m = SUBCLASS_RE.match(str(raw))
    if not m:
        return None
    return "".join(m.groups())


def _extract_rows(xls_path: Path) -> list[dict]:
    """Walk the workbook and emit one dict per CNAE subclass.

    Strategy: keep cursors for current Seção/Divisão/Grupo/Classe. A row whose first
    code cell matches the subclass pattern starts a new subclass. Subsequent rows whose
    first cell is empty append to the current subclass's notes_explicativas until a new
    code (any level) appears.
    """
    wb = load_workbook(xls_path, data_only=True)
    ws = wb.active

    current_secao: str | None = None
    current_divisao: str | None = None
    current_grupo: str | None = None
    current_classe: str | None = None
    current_subclass: dict | None = None
    rows: list[dict] = []
    note_buffer: list[str] = []

    def flush_subclass() -> None:
        nonlocal note_buffer
        if current_subclass is None:
            return
        full_notes = "\n".join(s for s in note_buffer if s).strip() or None
        current_subclass["notas_explicativas"] = full_notes
        current_subclass["exemplos_atividades"] = _extract_compreende(full_notes)
        rows.append(current_subclass)
        note_buffer = []

    for raw_row in ws.iter_rows(values_only=True):
        cells = [str(c).strip() if c is not None else "" for c in raw_row]
        if not any(cells):
            continue

        first = cells[0]

        if SECAO_RE.match(first):
            current_secao = first.strip()
            continue
        if DIVISAO_RE.match(first):
            current_divisao = first.strip()
            continue
        if GRUPO_RE.match(first):
            current_grupo = first.replace("-", ".").replace("/", ".").replace(".", "")[:3]
            continue
        if CLASSE_RE.match(first):
            current_classe = re.sub(r"\D", "", first)[:5]
            continue

        code = _norm_code(first)
        if code is not None:
            flush_subclass()
            denominacao = next((c for c in cells[1:] if c), "")
            current_subclass = {
                "codigo": code,
                "secao": current_secao,
                "divisao": current_divisao,
                "grupo": current_grupo,
                "classe": current_classe,
                "denominacao": denominacao,
                "notas_explicativas": None,
                "exemplos_atividades": None,
            }
            continue

        if current_subclass is not None:
            text = " ".join(c for c in cells if c).strip()
            if text:
                note_buffer.append(text)

    flush_subclass()
    return rows


def _extract_compreende(notes: str | None) -> str | None:
    """Extract only the bullets under 'Esta subclasse compreende:' / 'compreende também:'
    (stops at 'não compreende' or end). Returns None if the section isn't present.
    """
    if not notes:
        return None
    pattern = re.compile(
        r"esta subclasse compreende[^:\n]*:(.*?)"
        r"(?=esta subclasse não compreende|notas? explicativas?|$)",
        re.IGNORECASE | re.DOTALL,
    )
    chunks = [m.group(1).strip() for m in pattern.finditer(notes)]
    return "\n".join(chunks).strip() or None if chunks else None


def main() -> int:
    if not RAW_PATH.exists():
        print(
            f"ERROR: {RAW_PATH} not found.\n"
            "  Download the IBGE CNAE 2.3 Estrutura Detalhada XLSX from concla.ibge.gov.br\n"
            "  and place it at that exact path.",
            file=sys.stderr,
        )
        return 2

    rows = _extract_rows(RAW_PATH)
    print(f"Parsed {len(rows)} CNAE subclasses from {RAW_PATH.name}")
    if len(rows) != EXPECTED_COUNT:
        print(
            f"ERROR: expected {EXPECTED_COUNT} subclasses, got {len(rows)}. "
            "Check XLSX structure / parser regex.",
            file=sys.stderr,
        )
        return 1

    bad = [r for r in rows if not r["codigo"] or not r["denominacao"]]
    if bad:
        print(f"ERROR: {len(bad)} rows missing codigo/denominacao", file=sys.stderr)
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} entries to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
