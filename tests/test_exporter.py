"""csv_exporter, json_exporter 커버리지."""
import json
from datetime import date, datetime
from pathlib import Path

import pytest

from dummy_gen.exporter.csv_exporter import CsvExporter
from dummy_gen.exporter.json_exporter import JsonExporter


# ── CsvExporter ──────────────────────────────────────────────────────────────

def test_csv_normal(tmp_path):
    rows = [{"a": 1, "b": "hello"}, {"a": 2, "b": "world"}]
    out = CsvExporter().export(rows, tmp_path / "out.csv")
    lines = out.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "a,b"
    assert len(lines) == 3


def test_csv_empty_rows(tmp_path):
    out = CsvExporter().export([], tmp_path / "empty.csv")
    assert out.read_text() == ""


def test_csv_creates_parent_dirs(tmp_path):
    out = CsvExporter().export([{"x": 1}], tmp_path / "sub" / "dir" / "out.csv")
    assert out.exists()


# ── JsonExporter ─────────────────────────────────────────────────────────────

def test_json_normal(tmp_path):
    rows = [{"a": 1, "b": "hi"}]
    out = JsonExporter().export(rows, tmp_path / "out.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == rows


def test_json_datetime_serialized(tmp_path):
    rows = [{"ts": datetime(2024, 6, 1, 12, 0, 0), "d": date(2024, 1, 1)}]
    out = JsonExporter().export(rows, tmp_path / "out.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0]["ts"] == "2024-06-01T12:00:00"
    assert data[0]["d"] == "2024-01-01"


def test_json_non_serializable_raises(tmp_path):
    rows = [{"obj": object()}]
    with pytest.raises(TypeError):
        JsonExporter().export(rows, tmp_path / "out.json")
