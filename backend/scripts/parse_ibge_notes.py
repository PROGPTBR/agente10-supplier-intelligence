"""Parse the IBGE CNAE 2.3 explanatory notes PDF into a JSON keyed by CNAE 7-digit code.

The IBGE PDF (liv101721.pdf, ~600 pages) is structured per subclass:

    2021-5/00 Fabricação de produtos petroquímicos básicos
    Esta subclasse compreende:
    - a fabricação de produtos da primeira geração petroquímica como: eteno, propeno...
    Esta subclasse não compreende:
    - a fabricação de metano, etano, propano e butano (0600-0/01) e do refino (1921-7/00)
    - a fabricação de amônia (2012-6/00)

We extract:
- exemplos_atividades  ← text under "Esta subclasse compreende:" (positive)
- notas_explicativas   ← text under "Esta subclasse não compreende:" (negative;
                          critical for disambiguating sibling subclasses)

Output: backend/data/cnae_2.3/notas_ibge.json

Usage:
    uv run python scripts/parse_ibge_notes.py /path/to/liv101721.pdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber

SUBCLASS_RE = re.compile(r"^\s*(\d{4})-?(\d)/(\d{2})\s+(.+)$")
COMPREENDE_RE = re.compile(r"^\s*Esta\s+subclasse\s+compreende\s*:?\s*$", re.IGNORECASE)
NAO_COMPREENDE_RE = re.compile(
    r"^\s*Esta\s+subclasse\s+n[ãa]o\s+compreende\s*:?\s*$", re.IGNORECASE
)
PAGE_HEADER_RE = re.compile(
    r"^\s*Classifi?ca[çc][ãa]o\s+Nacional\s+de\s+Atividades", re.IGNORECASE
)
SECTION_HEADER_RE = re.compile(r"^\s*\d{2}\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ ]{6,}\s*$")
GROUP_HEADER_RE = re.compile(r"^\s*\d{2}\.\d\s+")
CLASS_HEADER_RE = re.compile(r"^\s*\d{2}\.\d{2}-\d\s+")


def _clean_line(s: str) -> str:
    # The IBGE PDF has hyphenation across word breaks: "petroquí-" + "micos" → "petroquímicos"
    return s.rstrip()


def _join_block(lines: list[str]) -> str:
    """Stitch the captured lines into a single paragraph, preserving bullet markers."""
    # Collapse hyphenated line breaks: "petroquí-\nmicos" → "petroquímicos"
    out: list[str] = []
    for line in lines:
        if out and out[-1].endswith("-") and line and not line[0].isupper():
            out[-1] = out[-1][:-1] + line.lstrip()
        else:
            out.append(line)
    return "\n".join(s for s in out if s.strip())


def parse_pdf(pdf_path: Path) -> dict[str, dict[str, str]]:
    """Return {codigo: {denominacao, exemplos_atividades, notas_explicativas}}."""
    entries: dict[str, dict[str, str]] = {}
    current_code: str | None = None
    current_denom: str = ""
    current_section: str | None = None  # 'compreende' or 'nao_compreende' or None
    compreende_buf: list[str] = []
    nao_compreende_buf: list[str] = []

    def flush() -> None:
        if current_code is None:
            return
        new_comp = _join_block(compreende_buf)
        new_nao = _join_block(nao_compreende_buf)
        # The PDF has 3 occurrences per subclass: TOC, summary list (no notes),
        # body (with notes), reverse index (codigo repeated as denom). Only
        # overwrite an existing entry if the new data has actual content.
        prev = entries.get(current_code)
        if prev and not (new_comp or new_nao):
            return  # keep the prior, richer entry
        entries[current_code] = {
            "denominacao": current_denom,
            "exemplos_atividades": new_comp,
            "notas_explicativas": new_nao,
        }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = _clean_line(raw_line)
                if not line.strip():
                    continue
                if PAGE_HEADER_RE.match(line):
                    continue
                # Skip pure hierarchy headers (division/group/class without subclass)
                if SECTION_HEADER_RE.match(line) or GROUP_HEADER_RE.match(line):
                    continue
                if CLASS_HEADER_RE.match(line):
                    continue

                m = SUBCLASS_RE.match(line)
                if m:
                    # New subclass — flush previous and start fresh
                    flush()
                    current_code = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                    current_denom = m.group(4).strip()
                    current_section = None
                    compreende_buf = []
                    nao_compreende_buf = []
                    continue

                if current_code is None:
                    continue

                if COMPREENDE_RE.match(line):
                    current_section = "compreende"
                    continue
                if NAO_COMPREENDE_RE.match(line):
                    current_section = "nao_compreende"
                    continue

                if current_section == "compreende":
                    compreende_buf.append(line)
                elif current_section == "nao_compreende":
                    nao_compreende_buf.append(line)

    flush()
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "cnae_2.3" / "notas_ibge.json",
    )
    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"ERROR: {args.pdf_path} not found", file=sys.stderr)
        return 2

    print(f"Parsing {args.pdf_path}...", flush=True)
    entries = parse_pdf(args.pdf_path)
    print(f"Extracted {len(entries)} subclasses", flush=True)

    # Stats: how many have non-empty content?
    with_comp = sum(1 for e in entries.values() if e["exemplos_atividades"])
    with_nao = sum(1 for e in entries.values() if e["notas_explicativas"])
    print(f"  with exemplos_atividades: {with_comp}")
    print(f"  with notas_explicativas (não compreende): {with_nao}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            [{"codigo": k, **v} for k, v in sorted(entries.items())],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {args.output} ({args.output.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
