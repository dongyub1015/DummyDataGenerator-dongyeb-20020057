from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from dummy_gen.config.loader import ConfigLoader
from dummy_gen.config.models import AppConfig, DatabaseConfig, GenerationConfig, TableConfig
from dummy_gen.connector.db_connector import DBConnector
from dummy_gen.inserter.batch_inserter import InsertResult
from dummy_gen.orchestrator import Orchestrator, RunOptions
from dummy_gen.schema.reader import SchemaReader

app = typer.Typer(
    name="dummy-gen",
    help="테스트용 더미 데이터를 생성하고 DB에 삽입하는 CLI 도구",
    add_completion=False,
)
console = Console()
_loader = ConfigLoader()
_connector = DBConnector()


def _setup_logging(log_file: str | None, no_progress: bool) -> None:
    from datetime import date
    import os

    log_path = log_file or f"logs/run_{date.today():%Y%m%d}.log"
    os.makedirs(Path(log_path).parent, exist_ok=True)

    fmt = logging.Formatter("[%(asctime)s] %(levelname)-5s %(message)s", "%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger("dummy_gen")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    if no_progress:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)


def _load_config(
    config: Path | None,
    dsn: str | None,
    tables: list[str],
    rows: int,
    mode: str,
    seed: int | None,
    batch_size: int,
    disable_fk: bool,
    locale: str,
) -> AppConfig:
    if config:
        return _loader.load(config)

    db_cfg = DatabaseConfig(dsn=dsn or "sqlite:///:memory:")
    if dsn and "postgresql" in dsn:
        db_cfg.driver = "postgresql"
    elif dsn and "mysql" in dsn:
        db_cfg.driver = "mysql"
    elif dsn and "mssql" in dsn:
        db_cfg.driver = "mssql"
    else:
        db_cfg.driver = "sqlite"

    gen_cfg = GenerationConfig(
        seed=seed, locale=locale, batch_size=batch_size, mode=mode, disable_fk=disable_fk
    )
    table_cfgs = [TableConfig(name=t, rows=rows) for t in tables]
    return AppConfig(database=db_cfg, generation=gen_cfg, tables=table_cfgs)


@app.command("run")
def cmd_run(
    config: Optional[Path] = typer.Option(None, "--config", help="YAML 설정 파일 경로"),
    dsn: Optional[str] = typer.Option(None, "--dsn", help="DB 연결 문자열"),
    table: list[str] = typer.Option([], "--table", help="대상 테이블 (반복 가능)"),
    rows: int = typer.Option(1000, "--rows", help="생성 건수"),
    mode: str = typer.Option("append", "--mode", help="append|truncate"),
    seed: Optional[int] = typer.Option(None, "--seed", help="랜덤 시드"),
    batch_size: int = typer.Option(1000, "--batch-size", help="배치 크기"),
    locale: str = typer.Option("ko_KR", "--locale", help="Faker 로케일"),
    disable_fk: bool = typer.Option(False, "--disable-fk", is_flag=True, help="FK 제약 비활성화"),
    dry_run: bool = typer.Option(False, "--dry-run", is_flag=True, help="삽입 없이 검증만"),
    no_progress: bool = typer.Option(False, "--no-progress", is_flag=True, help="CI 환경용"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="로그 파일 경로"),
) -> None:
    _setup_logging(log_file, no_progress)

    try:
        app_cfg = _load_config(config, dsn, table, rows, mode, seed, batch_size, disable_fk, locale)
        engine = _connector.connect(app_cfg.database)
    except Exception as exc:
        console.print(f"[red][오류][/red] {exc}")
        raise typer.Exit(2)

    opts = RunOptions(
        mode=app_cfg.generation.mode,
        disable_fk=app_cfg.generation.disable_fk,
        dry_run=dry_run,
        show_progress=not no_progress,
    )

    if not no_progress:
        from rich.progress import BarColumn, Progress, SpinnerColumn, TimeRemainingColumn
        with Progress(
            SpinnerColumn(),
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "{task.completed}/{task.total}",
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            tasks: dict[str, object] = {}

            def make_cb(tname: str, total: int):
                task_id = progress.add_task(f"[cyan]{tname}", total=total)
                tasks[tname] = task_id
                def cb(done: int, _total: int):
                    progress.update(task_id, completed=done)
                return cb

            for tbl_cfg in app_cfg.tables or []:
                opts.progress_cb = make_cb(tbl_cfg.name, tbl_cfg.rows)

            results = Orchestrator().run(engine, app_cfg, opts)
    else:
        results = Orchestrator().run(engine, app_cfg, opts)

    _print_summary(results)
    engine.dispose()

    if any(not r.success for r in results):
        raise typer.Exit(1)


@app.command("schema")
def cmd_schema(
    config: Optional[Path] = typer.Option(None, "--config", help="YAML 설정 파일 경로"),
    dsn: Optional[str] = typer.Option(None, "--dsn", help="DB 연결 문자열"),
    table: list[str] = typer.Option([], "--table", help="조회할 테이블 (생략 시 전체)"),
    fmt: str = typer.Option("table", "--format", help="출력 형식: table|json"),
) -> None:
    try:
        if config:
            app_cfg = _loader.load(config)
            engine = _connector.connect(app_cfg.database)
        elif dsn:
            engine = _connector.connect_dsn(dsn)
        else:
            console.print("[red]--config 또는 --dsn 이 필요합니다.[/red]")
            raise typer.Exit(3)
    except Exception as exc:
        console.print(f"[red][오류][/red] {exc}")
        raise typer.Exit(2)

    reader = SchemaReader()
    names = table or None
    metas = reader.read_tables(engine, names)
    engine.dispose()

    if fmt == "json":
        import json
        out = []
        for m in metas:
            out.append({
                "table": m.name,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.type_name,
                        "nullable": c.nullable,
                        "kind": c.kind.value,
                    }
                    for c in m.columns
                ],
            })
        console.print_json(json.dumps(out, ensure_ascii=False))
        return

    for meta in metas:
        t = Table(title=f"[bold]{meta.name}[/bold]  컬럼 {len(meta.columns)}개")
        t.add_column("Column", style="cyan")
        t.add_column("Type")
        t.add_column("Nullable")
        t.add_column("Constraint")
        for col in meta.columns:
            constraint = col.kind.value.upper() if col.kind.value != "normal" else ""
            nullable = "YES" if col.nullable else "NO"
            t.add_row(col.name, col.type_name, nullable, constraint)
        console.print(t)
        if meta.fk_relations:
            fk_txt = ", ".join(
                f"{fk.column} → {fk.ref_table}.{fk.ref_column}"
                for fk in meta.fk_relations
            )
            console.print(f"  FK 참조: {fk_txt}\n")


def _print_summary(results: list[InsertResult]) -> None:
    t = Table(title="삽입 결과")
    t.add_column("Table", style="cyan")
    t.add_column("Inserted", justify="right")
    t.add_column("Failed", justify="right")
    t.add_column("Elapsed", justify="right")
    t.add_column("Status")

    total_inserted = 0
    total_failed = 0
    total_elapsed = 0.0

    for r in results:
        status = "[green]OK[/green]" if r.success else "[red]FAIL[/red]"
        t.add_row(
            r.table,
            f"{r.inserted:,}",
            f"{r.failed:,}",
            f"{r.elapsed:.2f}s",
            status,
        )
        total_inserted += r.inserted
        total_failed += r.failed
        total_elapsed += r.elapsed

    t.add_section()
    t.add_row(
        "TOTAL",
        f"{total_inserted:,}",
        f"{total_failed:,}",
        f"{total_elapsed:.2f}s",
        "",
    )
    console.print(t)


@app.command("preview")
def cmd_preview(
    config: Optional[Path] = typer.Option(None, "--config", help="YAML 설정 파일 경로"),
    dsn: Optional[str] = typer.Option(None, "--dsn", help="DB 연결 문자열"),
    table: list[str] = typer.Option([], "--table", help="대상 테이블"),
    rows: int = typer.Option(10, "--rows", help="샘플 건수"),
    seed: Optional[int] = typer.Option(None, "--seed", help="랜덤 시드"),
    locale: str = typer.Option("ko_KR", "--locale"),
) -> None:
    try:
        app_cfg = _load_config(config, dsn, table, rows, "append", seed, rows, False, locale)
        engine = _connector.connect(app_cfg.database)
    except Exception as exc:
        console.print(f"[red][오류][/red] {exc}")
        raise typer.Exit(2)

    from dummy_gen.generator.factory import StrategyFactory
    from dummy_gen.schema.reader import SchemaReader as SR

    gen = app_cfg.generation
    reader = SR()
    factory = StrategyFactory()
    names = [t.name for t in app_cfg.tables] if app_cfg.tables else None
    metas = reader.read_tables(engine, names)
    table_cfgs = {t.name: t for t in app_cfg.tables}

    for meta in metas:
        tbl_cfg = table_cfgs.get(meta.name)
        col_cfgs = tbl_cfg.columns if tbl_cfg else {}
        from dummy_gen.schema.models import ColumnKind
        strategies = {}
        for col in meta.columns:
            if col.kind == ColumnKind.PK and not col_cfgs.get(col.name):
                continue
            col_cfg = col_cfgs.get(col.name)
            strategies[col.name] = factory.build(col, col_cfg, gen.seed, gen.locale, engine, rows)

        sample_rows = []
        for _ in range(rows):
            sample_rows.append({name: s.generate() for name, s in strategies.items()})

        t = Table(title=f"[bold]{meta.name}[/bold] 미리보기 ({rows}건)")
        if sample_rows:
            for col_name in sample_rows[0]:
                t.add_column(col_name, overflow="fold")
            for row in sample_rows:
                t.add_row(*[str(v) for v in row.values()])
        console.print(t)

    engine.dispose()


@app.command("export")
def cmd_export(
    config: Optional[Path] = typer.Option(None, "--config", help="YAML 설정 파일 경로"),
    dsn: Optional[str] = typer.Option(None, "--dsn", help="DB 연결 문자열"),
    table: list[str] = typer.Option([], "--table", help="대상 테이블"),
    rows: int = typer.Option(1000, "--rows", help="생성 건수"),
    fmt: str = typer.Option("csv", "--format", help="csv|json"),
    output: Path = typer.Option(Path("output"), "--output", help="출력 디렉토리"),
    seed: Optional[int] = typer.Option(None, "--seed"),
    locale: str = typer.Option("ko_KR", "--locale"),
    insert_also: bool = typer.Option(False, "--insert-also", is_flag=True),
) -> None:
    from datetime import datetime as _dt
    from dummy_gen.exporter.csv_exporter import CsvExporter
    from dummy_gen.exporter.json_exporter import JsonExporter
    from dummy_gen.generator.factory import StrategyFactory
    from dummy_gen.schema.models import ColumnKind

    try:
        app_cfg = _load_config(config, dsn, table, rows, "append", seed, 1000, False, locale)
        engine = _connector.connect(app_cfg.database)
    except Exception as exc:
        console.print(f"[red][오류][/red] {exc}")
        raise typer.Exit(2)

    gen = app_cfg.generation
    reader = SchemaReader()
    factory = StrategyFactory()
    names = [t.name for t in app_cfg.tables] if app_cfg.tables else None
    metas = reader.read_tables(engine, names)
    table_cfgs = {t.name: t for t in app_cfg.tables}
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")

    for meta in metas:
        tbl_cfg = table_cfgs.get(meta.name)
        tbl_rows = tbl_cfg.rows if tbl_cfg else rows
        col_cfgs = tbl_cfg.columns if tbl_cfg else {}
        strategies = {}
        for col in meta.columns:
            if col.kind == ColumnKind.PK and not col_cfgs.get(col.name):
                continue
            col_cfg = col_cfgs.get(col.name)
            strategies[col.name] = factory.build(col, col_cfg, gen.seed, gen.locale, engine, tbl_rows)

        generated = [{name: s.generate() for name, s in strategies.items()} for _ in range(tbl_rows)]

        suffix = fmt.lower()
        out_path = output / f"{meta.name}_{ts}.{suffix}"
        if fmt == "json":
            JsonExporter().export(generated, out_path)
        else:
            CsvExporter().export(generated, out_path)
        console.print(f"[green]내보내기 완료:[/green] {out_path} ({tbl_rows:,}건)")

        if insert_also:
            from dummy_gen.inserter.batch_inserter import BatchInserter
            result = BatchInserter().insert(engine, meta.name, generated, gen.batch_size)
            console.print(f"[green]삽입 완료:[/green] {meta.name} → {result.inserted:,}건")

    engine.dispose()


template_app = typer.Typer(help="설정 템플릿 관리")
app.add_typer(template_app, name="template")

_TEMPLATE_DIR = Path.home() / ".dummy_gen" / "templates"


@template_app.command("save")
def template_save(
    name: str = typer.Option(..., "--name", help="템플릿 이름"),
    config: Path = typer.Option(..., "--config", help="저장할 YAML 설정 파일"),
) -> None:
    _TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    dest = _TEMPLATE_DIR / f"{name}.yaml"
    dest.write_text(config.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]템플릿 저장:[/green] {dest}")


@template_app.command("list")
def template_list() -> None:
    if not _TEMPLATE_DIR.exists():
        console.print("저장된 템플릿이 없습니다.")
        return
    for f in sorted(_TEMPLATE_DIR.glob("*.yaml")):
        console.print(f"  {f.stem}")


@template_app.command("load")
def template_load(
    name: str = typer.Option(..., "--name", help="템플릿 이름"),
    output: Optional[Path] = typer.Option(None, "--output", help="저장할 경로"),
) -> None:
    src = _TEMPLATE_DIR / f"{name}.yaml"
    if not src.exists():
        console.print(f"[red]템플릿 '{name}'을 찾을 수 없습니다.[/red]")
        raise typer.Exit(3)
    dest = output or Path(f"{name}.yaml")
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]로드 완료:[/green] {dest}")


@template_app.command("delete")
def template_delete(
    name: str = typer.Option(..., "--name", help="템플릿 이름"),
) -> None:
    target = _TEMPLATE_DIR / f"{name}.yaml"
    if not target.exists():
        console.print(f"[red]템플릿 '{name}'을 찾을 수 없습니다.[/red]")
        raise typer.Exit(3)
    target.unlink()
    console.print(f"[green]삭제 완료:[/green] {name}")


if __name__ == "__main__":
    app()
