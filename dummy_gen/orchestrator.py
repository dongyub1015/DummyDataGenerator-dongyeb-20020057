from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine

from dummy_gen.config.models import AppConfig, GenerationConfig, TableConfig
from dummy_gen.generator.factory import StrategyFactory
from dummy_gen.inserter.batch_inserter import BatchInserter, InsertResult
from dummy_gen.schema.models import ColumnKind, TableMeta
from dummy_gen.schema.reader import SchemaReader

logger = logging.getLogger("dummy_gen")


@dataclass
class RunOptions:
    mode: str = "append"
    disable_fk: bool = False
    dry_run: bool = False
    show_progress: bool = True
    progress_cb: Any = None


class Orchestrator:

    def __init__(self):
        self._schema_reader = SchemaReader()
        self._factory = StrategyFactory()
        self._inserter = BatchInserter()

    def run(
        self,
        engine: Engine,
        config: AppConfig,
        options: RunOptions | None = None,
    ) -> list[InsertResult]:
        opts = options or RunOptions()
        gen = config.generation

        table_names = [t.name for t in config.tables] if config.tables else None
        table_metas = self._schema_reader.read_tables(engine, table_names)
        meta_map = {m.name: m for m in table_metas}

        table_cfgs = {t.name: t for t in config.tables}
        ordered_names = self._topological_sort(table_metas, opts.disable_fk)

        logger.info("삽입 순서: %s", " → ".join(ordered_names))

        pk_pools: dict[str, list] = {}
        results: list[InsertResult] = []

        for table_name in ordered_names:
            meta = meta_map[table_name]
            tbl_cfg = table_cfgs.get(table_name)
            row_count = tbl_cfg.rows if tbl_cfg else gen.batch_size

            rows = self._generate_rows(
                meta, tbl_cfg, gen, pk_pools, engine, row_count
            )

            if opts.dry_run:
                logger.info("[dry-run] %s: %d행 생성 (삽입 생략)", table_name, len(rows))
                results.append(InsertResult(table=table_name, inserted=0))
                continue

            logger.info("삽입 시작: %s (%d행)", table_name, row_count)
            result = self._inserter.insert(
                engine=engine,
                table_name=table_name,
                rows=rows,
                batch_size=gen.batch_size,
                mode=opts.mode,
                disable_fk=opts.disable_fk,
                progress_cb=opts.progress_cb,
            )
            results.append(result)
            logger.info(
                "삽입 완료: %s → %d건 (%.2fs)", table_name, result.inserted, result.elapsed
            )

            pk_cols = meta.pk_columns
            if pk_cols and rows:
                pk_col = pk_cols[0]
                pk_pools[table_name] = [r[pk_col] for r in rows if pk_col in r]

        return results

    def _generate_rows(
        self,
        meta: TableMeta,
        tbl_cfg: TableConfig | None,
        gen: GenerationConfig,
        pk_pools: dict[str, list],
        engine: Engine,
        row_count: int,
    ) -> list[dict]:
        col_cfgs = tbl_cfg.columns if tbl_cfg else {}
        strategies = {}

        for col in meta.columns:
            if col.kind == ColumnKind.PK and not col_cfgs.get(col.name):
                continue

            col_cfg = col_cfgs.get(col.name)

            if col.kind == ColumnKind.FK and col.fk and not col_cfg:
                from dummy_gen.generator.foreign_key_strategy import ForeignKeyStrategy
                fk_strategy = ForeignKeyStrategy(engine, col.fk.ref_table, col.fk.ref_column)
                pool = pk_pools.get(col.fk.ref_table)
                if pool:
                    fk_strategy.inject_pool(pool)
                strategies[col.name] = fk_strategy
                continue

            strategies[col.name] = self._factory.build(
                col=col,
                col_cfg=col_cfg,
                seed=gen.seed,
                locale=gen.locale,
                engine=engine,
                row_count=row_count,
            )

        rows = []
        for _ in range(row_count):
            row = {name: s.generate() for name, s in strategies.items()}
            rows.append(row)
        return rows

    def _topological_sort(
        self, tables: list[TableMeta], disable_fk: bool
    ) -> list[str]:
        table_set = {t.name for t in tables}
        in_degree: dict[str, int] = defaultdict(int)
        adj: dict[str, list[str]] = defaultdict(list)

        for table in tables:
            in_degree.setdefault(table.name, 0)
            for fk in table.fk_relations:
                ref = fk.ref_table
                if ref in table_set and ref != table.name:
                    adj[ref].append(table.name)
                    in_degree[table.name] += 1

        queue = deque(name for name in table_set if in_degree[name] == 0)
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(tables):
            cyclic = [t.name for t in tables if t.name not in order]
            if disable_fk:
                logger.warning(
                    "순환 FK 감지: %s — FK 비활성화 모드로 임의 순서로 삽입합니다.", cyclic
                )
                return order + cyclic
            raise RuntimeError(
                f"순환 FK 참조가 감지되었습니다: {cyclic}. "
                "--disable-fk 옵션으로 FK 제약을 비활성화하세요."
            )

        return order
