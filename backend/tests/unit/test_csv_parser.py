# backend/tests/unit/test_csv_parser.py
from pathlib import Path

import pytest

from agente10.estagio1.csv_parser import (
    CsvParseError,
    parse_catalog_bytes,
)


def test_parses_minimal_csv():
    csv = b"descricao_original\nParafuso M8\nGerador a diesel\n"
    rows = list(parse_catalog_bytes(csv, "catalogo.csv"))
    assert len(rows) == 2
    assert rows[0].descricao_original == "Parafuso M8"
    assert rows[0].agrupamento is None
    assert rows[0].extras == {}


def test_parses_full_catalog_columns():
    csv = (
        b"descricao_original,agrupamento,id_linha_origem,valor_total,obs_cliente\n"
        b"Parafuso M8,Parafusos,L1,150.50,Comprar mais\n"
    )
    [row] = list(parse_catalog_bytes(csv, "c.csv"))
    assert row.descricao_original == "Parafuso M8"
    assert row.agrupamento == "Parafusos"
    assert row.id_linha_origem == "L1"
    assert row.valor_total == "150.50"
    assert row.extras == {"obs_cliente": "Comprar mais"}


def test_missing_required_column_raises():
    csv = b"agrupamento\nParafusos\n"
    with pytest.raises(CsvParseError, match="descricao_original"):
        list(parse_catalog_bytes(csv, "c.csv"))


def test_empty_descricao_raises_when_row_has_other_content():
    # Row 2 has empty descricao but a value in another column → genuine error,
    # not a trailing-blank artifact from Excel-saved CSVs.
    csv = b"descricao_original,obs\n,note\nParafuso,ok\n"
    with pytest.raises(CsvParseError, match="line 2"):
        list(parse_catalog_bytes(csv, "c.csv"))


def test_entirely_blank_row_is_skipped():
    # Excel often appends trailing blank rows; parser must skip them silently.
    csv = b"descricao_original\n\nParafuso\n"
    [row] = list(parse_catalog_bytes(csv, "c.csv"))
    assert row.descricao_original == "Parafuso"


def test_cp1252_encoding_auto_detected():
    text = "descricao_original\nManutenção\n"
    csv_cp1252 = text.encode("cp1252")
    [row] = list(parse_catalog_bytes(csv_cp1252, "c.csv"))
    assert row.descricao_original == "Manutenção"


def test_xlsx_format(tmp_path: Path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["descricao_original", "agrupamento"])
    ws.append(["Parafuso M8", "Parafusos"])
    xlsx_path = tmp_path / "c.xlsx"
    wb.save(xlsx_path)
    rows = list(parse_catalog_bytes(xlsx_path.read_bytes(), "c.xlsx"))
    assert len(rows) == 1
    assert rows[0].agrupamento == "Parafusos"
