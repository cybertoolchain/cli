# src/toolchain/output.py
from __future__ import annotations

import csv
import io
import json
from typing import Any

from tabulate import tabulate

_PRIORITY_FIELDS = ("name", "tool", "display", "status", "severity", "category")
_DEEMPHASIZE_SUFFIXES = ("id", "uuid", "url", "href")


def extract_items(data: Any) -> list[dict] | None:
    """The largest list-of-dicts found anywhere in an arbitrary response, or
    None if there isn't one — lets table/csv/limit work without per-endpoint
    wiring, the same way Jon's other CLIs do it."""
    candidates: list[list[dict]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node):
                candidates.append(node)
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(data)
    if not candidates:
        return None
    return max(candidates, key=len)


def _priority_key(field: str) -> tuple[int, int, str]:
    lower = field.lower()
    if lower in _PRIORITY_FIELDS:
        return (0, _PRIORITY_FIELDS.index(lower), field)
    if lower.endswith(_DEEMPHASIZE_SUFFIXES):
        return (2, 0, field)
    return (1, 0, field)


def _reorder(row: dict) -> dict:
    return {key: row[key] for key in sorted(row, key=_priority_key)}


def _search_fields(data: Any, name: str) -> dict:
    matches: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == name:
                    matches.append(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return {"field": name, "count": len(matches), "values": matches}


def format_output(
    data: Any,
    *,
    fmt: str = "json",
    limit: int | None = None,
    search_fields: str | None = None,
    short: bool = False,
) -> str:
    if search_fields:
        data = _search_fields(data, search_fields)

    items = extract_items(data)
    if items is not None and limit is not None:
        items = items[:limit]
        if isinstance(data, dict):
            data = {**data}
            for key, value in list(data.items()):
                if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                    data[key] = items
                    break
        else:
            data = items

    if short:
        rows = items if items is not None else ([data] if isinstance(data, dict) else [])
        return "\n".join(json.dumps(_reorder(row), separators=(",", ":")) for row in rows)

    if fmt == "json":
        return json.dumps(data, indent=2)

    if items is None:
        raise ValueError(f"Cannot render {fmt} output: no list of records found in the response")

    if fmt == "table":
        return tabulate(items, headers="keys", tablefmt="grid")

    if fmt in ("csv", "tsv"):
        buffer = io.StringIO()
        delimiter = "," if fmt == "csv" else "\t"
        fieldnames = sorted({key for row in items for key in row})
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(items)
        return buffer.getvalue()

    raise ValueError(f"Unsupported output format: {fmt}")
