"""Unit tests for load_empresas.py — tests the transform with SQLite in-memory.

The real ingestion needs the upstream rictom-produced SQLite (~30GB). This test
builds a tiny equivalent in-memory and validates the SQL JOIN + filters work.
Postgres UPSERT is not exercised here (covered by integration via shape tests).
"""

import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from load_empresas import build_empresa_rows


@pytest.fixture()
def sqlite_with_2_empresas():
    """SQLite in-memory with the minimal schema rictom produces.

    Mirrors rictom/cnpj-sqlite v0.7 schema (verified against real cnpj.db
    on 2026-05-12): table `empresas` (plural), column `cnae_fiscal` (not
    cnae_fiscal_principal), columns `ddd1`/`telefone1` (no underscore),
    and estabelecimento has a denormalized `cnpj` column.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE empresas (
            cnpj_basico TEXT PRIMARY KEY,
            razao_social TEXT,
            natureza_juridica TEXT,
            porte_empresa TEXT,
            capital_social REAL
        );
        CREATE TABLE estabelecimento (
            cnpj_basico TEXT,
            cnpj_ordem TEXT,
            cnpj_dv TEXT,
            nome_fantasia TEXT,
            situacao_cadastral TEXT,
            data_inicio_atividades TEXT,
            cnae_fiscal TEXT,
            cnae_fiscal_secundaria TEXT,
            tipo_logradouro TEXT, logradouro TEXT, numero TEXT,
            complemento TEXT, bairro TEXT,
            cep TEXT, uf TEXT, municipio TEXT,
            ddd1 TEXT, telefone1 TEXT,
            correio_eletronico TEXT,
            cnpj TEXT
        );
        CREATE TABLE municipio (codigo TEXT PRIMARY KEY, descricao TEXT);

        INSERT INTO empresas VALUES
            ('11111111', 'EMPRESA ATIVA SA', '2062', '03', 100000.0),
            ('22222222', 'EMPRESA BAIXADA LTDA', '2062', '01', 50000.0);

        INSERT INTO estabelecimento VALUES
            ('11111111', '0001', '01', 'Fantasia', '02', '20100101',
             '4744001', '4673700,4684201',
             'Rua', 'A', '1', '', 'Centro',
             '01000000', 'SP', '7107',
             '11', '999999999', 'a@b.com',
             '11111111000101'),
            ('22222222', '0001', '02', '', '08', '20050505',
             '4744001', '',
             'Rua', 'B', '2', '', 'Bairro',
             '02000000', 'RJ', '6001',
             '21', '888888888', '',
             '22222222000102');

        INSERT INTO municipio VALUES
            ('7107', 'Sao Paulo'),
            ('6001', 'Rio de Janeiro');
        """)
    yield conn
    conn.close()


def test_filters_only_ativa(sqlite_with_2_empresas):
    rows = list(build_empresa_rows(sqlite_with_2_empresas))
    # Only the situacao_cadastral='02' row should be present
    assert len(rows) == 1
    assert rows[0]["cnpj"] == "11111111000101"


def test_denormalized_fields(sqlite_with_2_empresas):
    [row] = list(build_empresa_rows(sqlite_with_2_empresas))
    assert row["razao_social"] == "EMPRESA ATIVA SA"
    assert row["nome_fantasia"] == "Fantasia"
    assert row["cnae_primario"] == "4744001"
    assert row["cnaes_secundarios"] == ["4673700", "4684201"]
    assert row["situacao_cadastral"] == "ATIVA"
    assert row["data_abertura"] == date(2010, 1, 1)
    assert row["porte"] == "EPP"
    assert row["uf"] == "SP"
    assert row["municipio"] == "Sao Paulo"
    assert row["telefone"] == "11999999999"
    assert row["email"] == "a@b.com"
    assert row["geom"] is None


def test_handles_empty_secondary_cnaes(sqlite_with_2_empresas):
    # Insert a 3rd row with no secondaries and re-query
    sqlite_with_2_empresas.execute(
        """INSERT INTO empresas VALUES ('33333333','SOLO LTDA','2062','01',10000)"""
    )
    sqlite_with_2_empresas.execute("""INSERT INTO estabelecimento VALUES
            ('33333333','0001','03','','02','20200101',
             '4744001','',
             'Rua','C','3','','',
             '03000000','MG','9999',
             '31','7','x@y.com',
             '33333333000103')""")
    sqlite_with_2_empresas.execute("""INSERT INTO municipio VALUES ('9999','Belo Horizonte')""")
    rows = [
        r for r in build_empresa_rows(sqlite_with_2_empresas) if r["cnpj"].startswith("33333333")
    ]
    assert len(rows) == 1
    assert rows[0]["cnaes_secundarios"] == []


def test_handles_unknown_municipio_code(sqlite_with_2_empresas):
    """When estabelecimento.municipio has no match in the municipio lookup table,
    the LEFT JOIN should produce row['municipio'] = None."""
    sqlite_with_2_empresas.execute(
        """INSERT INTO empresas VALUES ('44444444','UNKNOWN MUN LTDA','2062','01',5000)"""
    )
    sqlite_with_2_empresas.execute("""INSERT INTO estabelecimento VALUES
            ('44444444','0001','04','','02','20210515',
             '4744001','',
             'Rua','D','4','','',
             '04000000','GO','XXXX',
             '62','3','z@y.com',
             '44444444000104')""")
    # Note: NO matching INSERT into municipio table — the code 'XXXX' doesn't exist
    rows = [
        r for r in build_empresa_rows(sqlite_with_2_empresas) if r["cnpj"].startswith("44444444")
    ]
    assert len(rows) == 1
    assert rows[0]["municipio"] is None
