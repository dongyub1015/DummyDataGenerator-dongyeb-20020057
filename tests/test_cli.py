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


def test_run_with_progress_bar(config_file: Path):
    """--no-progress 없이 실행 → progress bar 분기 실행."""
    result = runner.invoke(app, ["run", "--config", str(config_file)])
    assert result.exit_code == 0


def test_run_with_failed_inserts_exits_1(tmp_path: Path):
    """삽입 실패 건이 있으면 exit code 1."""
    from sqlalchemy import create_engine, text as sqlt
    db = tmp_path / "fail.db"
    e = create_engine(f"sqlite:///{db}")
    with e.begin() as conn:
        conn.execute(sqlt("CREATE TABLE t (id INTEGER PRIMARY KEY NOT NULL)"))
        conn.execute(sqlt("INSERT INTO t VALUES (1)"))
    e.dispose()

    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(textwrap.dedent(f"""
        database:
          driver: sqlite
          dbname: {db}
        tables:
          - name: t
            rows: 1
            columns:
              id:
                strategy: fixed
                value: 1
    """), encoding="utf-8")
    result = runner.invoke(app, ["run", "--config", str(cfg), "--no-progress"])
    assert result.exit_code == 1


def test_schema_no_config_or_dsn():
    """--config도 --dsn도 없으면 exit 3."""
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 3


def test_schema_with_config(config_file: Path):
    """--config 경로로 schema 실행 (lines 162-163 커버)."""
    result = runner.invoke(app, ["schema", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "products" in result.output


def test_schema_connection_error(tmp_path: Path):
    """schema에서 연결 오류 발생 시 exit 2 (lines 166-168 커버)."""
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(textwrap.dedent("""
        database:
          driver: postgresql
          host: nonexistent_host_xyz_abc
          port: 5432
          user: u
          password: p
          dbname: db
    """), encoding="utf-8")
    result = runner.invoke(app, ["schema", "--config", str(cfg)])
    assert result.exit_code == 2


def test_schema_with_fk(tmp_path: Path):
    """FK 관계가 있는 테이블의 schema 출력에 FK 라인이 포함된다."""
    db = tmp_path / "fk.db"
    from sqlalchemy import create_engine, text as sqlt
    e = create_engine(f"sqlite:///{db}")
    with e.begin() as conn:
        conn.execute(sqlt("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        conn.execute(sqlt("CREATE TABLE child (id INTEGER PRIMARY KEY, pid INTEGER REFERENCES parent(id))"))
    e.dispose()

    result = runner.invoke(app, ["schema", "--dsn", f"sqlite:///{db}"])
    assert result.exit_code == 0
    assert "FK" in result.output or "pid" in result.output


def test_preview_no_config_error():
    """잘못된 DSN은 exit 2."""
    result = runner.invoke(app, ["preview", "--dsn", "sqlite:///no/such/dir/x.db", "--table", "t"])
    assert result.exit_code == 2


def test_export_with_insert_also(config_file: Path, tmp_path: Path, sqlite_db: Path):
    """--insert-also 플래그로 파일 내보내기와 DB 삽입 동시 실행."""
    out_dir = tmp_path / "out"
    result = runner.invoke(app, [
        "export", "--config", str(config_file),
        "--format", "csv", "--output", str(out_dir),
        "--insert-also",
    ])
    assert result.exit_code == 0
    assert "Insert done" in result.output or "rows" in result.output.lower()


def test_export_bad_dsn(tmp_path: Path):
    result = runner.invoke(app, ["export", "--dsn", "sqlite:///no/dir/x.db", "--table", "t"])
    assert result.exit_code == 2


def test_load_config_postgresql_dsn():
    """DSN에 postgresql 포함 → driver=postgresql 분기."""
    from dummy_gen.cli import _load_config
    cfg = _load_config(None, "postgresql://u:p@localhost/db", ["t"], 10, "append", None, 100, False, "en_US")
    assert cfg.database.driver == "postgresql"


def test_load_config_mysql_dsn():
    from dummy_gen.cli import _load_config
    cfg = _load_config(None, "mysql://u:p@localhost/db", ["t"], 10, "append", None, 100, False, "en_US")
    assert cfg.database.driver == "mysql"


def test_load_config_mssql_dsn():
    from dummy_gen.cli import _load_config
    cfg = _load_config(None, "mssql://u:p@localhost/db", ["t"], 10, "append", None, 100, False, "en_US")
    assert cfg.database.driver == "mssql"


def test_template_save_list_load_delete(tmp_path: Path, config_file: Path, monkeypatch):
    """template 서브커맨드 save → list → load → delete 흐름."""
    import dummy_gen.cli as cli_mod
    tpl_dir = tmp_path / "templates"
    monkeypatch.setattr(cli_mod, "_TEMPLATE_DIR", tpl_dir)

    result = runner.invoke(app, ["template", "save", "--name", "mytest", "--config", str(config_file)])
    assert result.exit_code == 0

    result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 0
    assert "mytest" in result.output

    out_cfg = tmp_path / "loaded.yaml"
    result = runner.invoke(app, ["template", "load", "--name", "mytest", "--output", str(out_cfg)])
    assert result.exit_code == 0
    assert out_cfg.exists()

    result = runner.invoke(app, ["template", "delete", "--name", "mytest"])
    assert result.exit_code == 0
    assert not (tpl_dir / "mytest.yaml").exists()


def test_template_load_not_found(tmp_path: Path, monkeypatch):
    import dummy_gen.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_TEMPLATE_DIR", tmp_path / "templates")
    result = runner.invoke(app, ["template", "load", "--name", "ghost"])
    assert result.exit_code == 3


def test_template_delete_not_found(tmp_path: Path, monkeypatch):
    import dummy_gen.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_TEMPLATE_DIR", tmp_path / "templates")
    result = runner.invoke(app, ["template", "delete", "--name", "ghost"])
    assert result.exit_code == 3


def test_template_list_empty(tmp_path: Path, monkeypatch):
    import dummy_gen.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_TEMPLATE_DIR", tmp_path / "empty_templates")
    result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 0
    assert "No templates" in result.output
