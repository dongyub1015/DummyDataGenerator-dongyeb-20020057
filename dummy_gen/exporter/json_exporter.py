from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path


def _default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"직렬화 불가 타입: {type(obj)}")


class JsonExporter:

    def export(self, rows: list[dict], output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2, default=_default)
        return path
