"""Data manipulation tools: csv_query."""

from __future__ import annotations

import csv
import io
import operator
from typing import Any


def _parse_csv(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    rows = list(reader)
    headers = list(reader.fieldnames or [])
    return headers, rows


def _cast(value: str) -> Any:
    """Try to cast a CSV string value to int/float; fall back to str."""
    for fn in (int, float):
        try:
            return fn(value)
        except (ValueError, TypeError):
            pass
    return value


async def run_csv_query(
    csv_text: str,
    select: list[str] | None = None,
    filter_col: str | None = None,
    filter_op: str | None = None,
    filter_val: str | None = None,
    limit: int = 100,
) -> dict:
    """Query a CSV string — select columns, filter rows, limit output.

    Args:
        csv_text: Raw CSV content (with header row).
        select: Column names to include. None = all columns.
        filter_col: Column to filter on.
        filter_op: One of: eq, ne, gt, lt, gte, lte, contains.
        filter_val: Value to compare against.
        limit: Max rows returned (capped at 500).

    Returns:
        {"columns": [...], "rows": [...], "total_matched": int}
    """
    try:
        headers, rows = _parse_csv(csv_text)
    except Exception as exc:
        return {"error": f"CSV parse failed: {exc}", "columns": [], "rows": [], "total_matched": 0}

    # Filter
    if filter_col and filter_op and filter_val is not None:
        _ops = {
            "eq": operator.eq,
            "ne": operator.ne,
            "gt": operator.gt,
            "lt": operator.lt,
            "gte": operator.ge,
            "lte": operator.le,
        }
        filtered = []
        for row in rows:
            cell = _cast(row.get(filter_col, ""))
            val = _cast(filter_val)
            if filter_op == "contains":
                if str(val).lower() in str(cell).lower():
                    filtered.append(row)
            elif filter_op in _ops:
                try:
                    if _ops[filter_op](cell, val):
                        filtered.append(row)
                except TypeError:
                    if _ops[filter_op](str(cell), str(val)):
                        filtered.append(row)
        rows = filtered

    total = len(rows)
    limit = min(limit, 500)
    rows = rows[:limit]

    # Select columns
    columns = select if select else headers
    result_rows = [{col: row.get(col, "") for col in columns} for row in rows]

    return {"columns": columns, "rows": result_rows, "total_matched": total}
