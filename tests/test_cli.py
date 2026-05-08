"""CLI 서브커맨드 동작 검증 (Typer CliRunner)."""
import textwrap
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from dummy_gen.cli import app

runner = CliRunner()


@pytest.fixture
def sqlite_db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    e = create_engine(f"sqlite:///{db_path}")
    with e.begin() as conn:
        conn.execute(text("""
            CREATE TABLE products (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  VARCHAR(100),
                price REAL,
                stock INTEGER
            )
        """))
    e.dispose()
    return db_path


@pytest.fixture
def config_file(tmp_path: Path, sqlite_db: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(textwrap.dedent(f"""
        database:
          driver: sqlite
          dbname: {sqlite_db}
        generation:
          seed: 1
          batch_size: 10
        tables:
          - name: products
            rows: 5
    """), encoding="utf-8")
    return cfg


def test_run_with_config(config_file: Path):
    result = runner.invoke(app, ["run", "--config", str(config_file), "--no-progress"])
    assert result.exit_code == 0
    assert "products" in result.output


def test_run_dry_run(config_file: Path):
    result = runner.invoke(app, ["run", "--config", str(config_file), "--dry-run", "--no-progress"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_schema_command(sqlite_db: Path):
    result = runner.invoke(app, ["schema", "--dsn", f"sqlite:///{sqlite_db}"])
    assert result.exit_code == 0
    assert "products" in result.output


def test_preview_command(sqlite_db: Path):
    result = runner.invoke(app, ["preview", "--dsn", f"sqlite:///{sqlite_db}", "--table", "products", "--rows", "3"])
    assert result.exit_code == 0
    assert "products" in result.output


def test_export_csv(config_file: Path, tmp_path: Path):
    out_dir = tmp_path / "out"
    result = runner.invoke(app, [
        "export", "--config", str(config_file),
        "--format", "csv", "--output", str(out_dir),
    ])
    assert result.exit_code == 0
    csv_files = list(out_dir.glob("*.csv"))
    assert len(csv_files) == 1


def test_export_json(config_file: Path, tmp_path: Path):
    out_dir = tmp_path / "out"
    result = runner.invoke(app, [
        "export", "--config", str(config_file),
        "--format", "json", "--output", str(out_dir),
    ])
    assert result.exit_code == 0
    json_files = list(out_dir.glob("*.json"))
    assert len(json_files) == 1


def test_run_bad_dsn():
    result = runner.invoke(app, ["run", "--dsn", "sqlite:///nonexistent_dir/x/test.db", "--table", "t"])
    assert result.exit_code != 0


def test_schema_json_format(sqlite_db: Path):
    result = runner.invoke(app, ["schema", "--dsn", f"sqlite:///{sqlite_db}", "--format", "json"])
    assert result.exit_code == 0
    assert '"table"' in result.output or "products" in result.output
