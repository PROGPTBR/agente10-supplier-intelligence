"""Unit tests for transform helpers used by load_empresas.py."""

import sys
from datetime import date
from pathlib import Path

import pytest

# Allow importing from scripts/ without installing as a package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from empresas_helpers import parse_porte, parse_yyyymmdd


class TestParseYYYYMMDD:
    def test_valid_date(self):
        assert parse_yyyymmdd("20040101") == date(2004, 1, 1)

    def test_none_returns_none(self):
        assert parse_yyyymmdd(None) is None

    def test_empty_string_returns_none(self):
        assert parse_yyyymmdd("") is None

    def test_zero_padded_returns_none(self):
        assert parse_yyyymmdd("00000000") is None

    def test_malformed_returns_none(self):
        assert parse_yyyymmdd("abc") is None
        assert parse_yyyymmdd("2004") is None


class TestParsePorte:
    @pytest.mark.parametrize(
        "code,expected",
        [
            ("00", None),
            ("01", "ME"),
            ("03", "EPP"),
            ("05", "DEMAIS"),
            ("", None),
            (None, None),
            ("99", None),
        ],
    )
    def test_mapping(self, code, expected):
        assert parse_porte(code) == expected
