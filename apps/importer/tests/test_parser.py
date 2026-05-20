"""Tests for the OpenCart SQL streaming parser."""

import pytest

from apps.importer.management.commands.import_opencart_sql import _cast, parse_values


class TestCast:
    def test_null_returns_none(self):
        assert _cast("NULL") is None

    def test_quoted_string(self):
        assert _cast("'hello'") == "hello"

    def test_escaped_quote(self):
        assert _cast("'it\\'s'") == "it's"

    def test_plain_number(self):
        assert _cast("42") == "42"


class TestParseValues:
    def test_simple_row(self):
        rows = parse_values("(1,'hello',NULL)")
        assert rows == [["1", "hello", None]]

    def test_multi_row(self):
        rows = parse_values("(1,'a'),(2,'b')")
        assert len(rows) == 2
        assert rows[0][0] == "1"
        assert rows[1][1] == "b"

    def test_comma_in_string(self):
        rows = parse_values("(1,'hello, world')")
        assert rows[0][1] == "hello, world"
