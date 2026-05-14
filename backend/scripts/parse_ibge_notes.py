"""Parse the IBGE CNAE 2.3 explanatory notes PDF into per-subclass + hierarchy JSON.

The IBGE PDF (liv101721.pdf, ~600 pages) has 3 levels of explanatory text:

    21 FABRICAÇÃO DE PRODUTOS QUÍMICOS                  ← Divisão
        intro paragraph describing the whole division

    20.21-5 Fabricação de produtos petroquímicos        ← Classe (Grupo header
        intro for the class                                shown as 20.2 prefix)

    2021-5/00 Fabricação de produtos petroquímicos básicos  ← Subclasse
    Esta subclasse compreende:                            ← exemplos_atividades
    - a fabricação de produtos da primeira geração petroquímica...
    Esta subclasse não compreende:                        ← notas_explicativas
    - a fabricação de metano (0600-0/01)...

We extract all three levels. Output JSON has:
    [
      {"codigo": "2021500", "denominacao": "...",
       "exemplos_atividades": "...", "notas_explicativas": "...",
       "divisao": "20", "divisao_descricao": "FABRICAÇÃO DE PRODUTOS QUÍMICOS\\n...",
       "grupo": "202", "grupo_descricao": "..."}
    ]

Hierarchy intros help the curator pick the right CNAE when leaf denominações
are ambiguous (e.g., "Manutenção..." appears in 6 different divisions).

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
# Divisão header: "20 FABRICAÇÃO DE PRODUTOS QUÍMICOS" — 2 digits + uppercase title
DIVISAO_RE = re.compile(r"^\s*(\d{2})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ \-,]{4,})\s*$")
SECTION_HEADER_RE = DIVISAO_RE  # alias kept for back-compat in code paths below
# Grupo header: "20.2 FABRICAÇÃO DE PRODUTOS QUÍMICOS ORGÂNICOS"
GROUP_HEADER_RE = re.compile(
    r"^\s*(\d{2}\.\d)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ \-,]{4,})\s*$"
)
# Classe header: "20.21-5 Fabricação de produtos petroquímicos básicos" (mixed case)
CLASS_HEADER_RE = re.compile(r"^\s*(\d{2}\.\d{2}-\d)\s+(.+)$")


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
    """Return {codigo: {denominacao, exemplos_atividades, notas_explicativas,
    divisao, divisao_descricao, grupo, grupo_descricao}}.
    """
    entries: dict[str, dict[str, str]] = {}
    current_code: str | None = None
    current_denom: str = ""
    current_section: str | None = None  # 'compreende' | 'nao_compreende' | 'div' | 'grp' | None
    compreende_buf: list[str] = []
    nao_compreende_buf: list[str] = []

    # Hierarchy state — captured from headers, applied to subsequent subclasses
    current_divisao: str = ""
    current_divisao_desc_buf: list[str] = []
    current_grupo: str = ""
    current_grupo_desc_buf: list[str] = []
    # Captured descriptions per division/group code (richer overwrites poorer)
    divisao_descs: dict[str, str] = {}
    grupo_descs: dict[str, str] = {}

    def flush() -> None:
        if current_code is None:
            return
        new_comp = _join_block(compreende_buf)
        new_nao = _join_block(nao_compreende_buf)
        # PDF has up to 4 occurrences per subclass; only overwrite if richer.
        prev = entries.get(current_code)
        if prev and not (new_comp or new_nao):
            return
        entries[current_code] = {
            "denominacao": current_denom,
            "exemplos_atividades": new_comp,
            "notas_explicativas": new_nao,
            "divisao": current_divisao,
            "divisao_descricao": divisao_descs.get(current_divisao, ""),
            "grupo": current_grupo,
            "grupo_descricao": grupo_descs.get(current_grupo, ""),
        }

    def flush_divisao_desc() -> None:
        if current_divisao and current_divisao_desc_buf:
            joined = _join_block(current_divisao_desc_buf)
            # Only overwrite if longer/richer
            if joined and (
                current_divisao not in divisao_descs
                or len(joined) > len(divisao_descs[current_divisao])
            ):
                divisao_descs[current_divisao] = joined

    def flush_grupo_desc() -> None:
        if current_grupo and current_grupo_desc_buf:
            joined = _join_block(current_grupo_desc_buf)
            if joined and (
                current_grupo not in grupo_descs
                or len(joined) > len(grupo_descs[current_grupo])
            ):
                grupo_descs[current_grupo] = joined

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = _clean_line(raw_line)
                if not line.strip():
                    continue
                if PAGE_HEADER_RE.match(line):
                    continue

                # Divisão header — capture code + start collecting intro
                div_m = DIVISAO_RE.match(line)
                if div_m:
                    flush_divisao_desc()
                    flush_grupo_desc()
                    current_divisao = div_m.group(1)
                    current_divisao_desc_buf = [div_m.group(2).strip()]
                    current_grupo = ""
                    current_grupo_desc_buf = []
                    current_section = "div"
                    continue

                # Grupo header — capture code + start collecting intro
                grp_m = GROUP_HEADER_RE.match(line)
                if grp_m:
                    flush_grupo_desc()
                    raw_grp = grp_m.group(1)  # e.g. "20.2"
                    current_grupo = raw_grp.replace(".", "")  # "202" — matches DB grupo column
                    current_grupo_desc_buf = [grp_m.group(2).strip()]
                    current_section = "grp"
                    continue

                # Classe header — ignored as a target (subclass detail follows),
                # but switches us OUT of div/grp text capture
                if CLASS_HEADER_RE.match(line):
                    flush_divisao_desc()
                    flush_grupo_desc()
                    current_section = None
                    continue

                m = SUBCLASS_RE.match(line)
                if m:
                    flush()
                    flush_divisao_desc()
                    flush_grupo_desc()
                    current_code = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                    current_denom = m.group(4).strip()
                    current_section = None
                    compreende_buf = []
                    nao_compreende_buf = []
                    continue

                # While inside a divisão/grupo intro block, accumulate text
                # (will stop at next divisão/grupo/classe/subclasse header).
                if current_section == "div":
                    current_divisao_desc_buf.append(line.strip())
                    continue
                if current_section == "grp":
                    current_grupo_desc_buf.append(line.strip())
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
    flush_divisao_desc()
    flush_grupo_desc()
    # Re-apply collected hierarchy descriptions to entries (since divisão text
    # can be parsed AFTER the subclasses that belong to it on subsequent pages)
    for code, e in entries.items():
        if e.get("divisao") and not e.get("divisao_descricao"):
            e["divisao_descricao"] = divisao_descs.get(e["divisao"], "")
        if e.get("grupo") and not e.get("grupo_descricao"):
            e["grupo_descricao"] = grupo_descs.get(e["grupo"], "")
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
    with_div = sum(1 for e in entries.values() if e.get("divisao_descricao"))
    with_grp = sum(1 for e in entries.values() if e.get("grupo_descricao"))
    print(f"  with exemplos_atividades: {with_comp}")
    print(f"  with notas_explicativas (não compreende): {with_nao}")
    print(f"  with divisao_descricao: {with_div}")
    print(f"  with grupo_descricao: {with_grp}")

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
