# src/toolchain/output.py
from __future__ import annotations

import copy
import csv
import io
import json
import re
from typing import Any

import click
from tabulate import tabulate

from .colors import PALETTES
from .models import UserInputError

_PRIORITY_FIELDS = ("name", "tool", "display", "status", "severity", "category")
_DEEMPHASIZE_SUFFIXES = ("id", "uuid", "url", "href")

#: One token per match: a "key": string (with its trailing colon captured
#: separately so it isn't colored), a bare string value, a number, or a
#: true/false/null literal. Alternatives are tried left-to-right, so a
#: quoted string is always consumed whole before the number/literal
#: branches get a chance — safe for json.dumps output, which never emits
#: an unescaped `"` inside a string.
_JSON_TOKEN_RE = re.compile(
    r'(?P<string>"(?:\\.|[^"\\])*")(?P<colon>\s*:)?'
    r"|(?P<number>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"|(?P<literal>\btrue\b|\bfalse\b|\bnull\b)"
)


def highlight_json(text: str, mode: str) -> str:
    """Colors json.dumps output with the brand palette for `mode`: keys in
    teal, string values in blue, numbers in amber, true/false/null in
    magenta. click strips these automatically when stdout isn't a tty, so
    piped/redirected JSON is unaffected."""
    palette = PALETTES[mode]

    def replace(match: re.Match) -> str:
        if match.group("string") is not None:
            colon = match.group("colon") or ""
            color = palette["teal"] if colon else palette["blue"]
            return click.style(match.group("string"), fg=color) + colon
        if match.group("number") is not None:
            return click.style(match.group("number"), fg=palette["amber"])
        return click.style(match.group("literal"), fg=palette["magenta"])

    return _JSON_TOKEN_RE.sub(replace, text)


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


def _find_path(node: Any, target: list, path: tuple = ()) -> tuple | None:
    """Where `target` (the exact list object extract_items found, matched
    by identity) actually lives inside `node` — a sequence of dict keys
    and/or list indices from `node` down to it. None if not found."""
    if node is target:
        return path
    if isinstance(node, dict):
        for key, value in node.items():
            found = _find_path(value, target, path + (key,))
            if found is not None:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _find_path(value, target, path + (index,))
            if found is not None:
                return found
    return None


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
    mode: str = "dark",
) -> str:
    if search_fields:
        data = _search_fields(data, search_fields)

    items = extract_items(data)
    if items is not None and limit is not None:
        truncated = items[:limit]
        path = _find_path(data, items)
        if path is None or path == ():
            # Either items came from nowhere findable (shouldn't happen,
            # since extract_items just pulled it from data) or data IS the
            # target list itself — either way, the truncated list is the
            # whole new response.
            data = truncated
        else:
            # Deep-copy first, THEN walk the recorded path into the copy —
            # walking the ORIGINAL data and mutating in place would corrupt
            # the `items` reference other code below still reads.
            data = copy.deepcopy(data)
            container = data
            for key in path[:-1]:
                container = container[key]
            container[path[-1]] = truncated
        items = truncated

    if short:
        rows = items if items is not None else ([data] if isinstance(data, dict) else [])
        text = "\n".join(json.dumps(_reorder(row), separators=(",", ":")) for row in rows)
        return highlight_json(text, mode)

    if fmt == "json":
        return highlight_json(json.dumps(data, indent=2), mode)

    if items is None:
        raise UserInputError(
            f"Cannot render {fmt} output: this response has no list of records "
            "(try -o json instead)"
        )

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
