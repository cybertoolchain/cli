# tests/test_output.py
from __future__ import annotations

import json

import click
from hypothesis import given
from hypothesis import strategies as st

from toolchain.models import UserInputError
from toolchain.output import extract_items, format_output


def _plain(out: str) -> str:
    """format_output() colors JSON with ANSI (click.echo strips it for
    non-tty/piped output at the real call sites, but these tests call
    format_output() directly)."""
    return click.unstyle(out)

TOOLS_RESPONSE = {
    "tools": [
        {"name": "Nmap", "category": "reconnaissance", "url": "https://nmap.org"},
        {"name": "Falco", "category": "runtime-security", "url": "https://falco.org"},
    ],
    "total": 2,
    "next_cursor": None,
}


def test_extract_items_finds_the_list_of_dicts():
    assert extract_items(TOOLS_RESPONSE) == TOOLS_RESPONSE["tools"]


def test_extract_items_none_when_no_list_present():
    assert extract_items({"total": 2}) is None


def test_extract_items_picks_the_largest_list():
    data = {"a": [{"x": 1}], "b": [{"y": 1}, {"y": 2}, {"y": 3}]}
    assert extract_items(data) == data["b"]


def test_json_is_the_default_format():
    out = format_output(TOOLS_RESPONSE)
    assert json.loads(_plain(out)) == TOOLS_RESPONSE


def test_json_output_is_indented():
    out = format_output({"a": 1}, fmt="json")
    assert _plain(out) == '{\n  "a": 1\n}'


def test_table_renders_a_grid_with_headers():
    out = format_output(TOOLS_RESPONSE, fmt="table")
    assert "name" in out
    assert "Nmap" in out
    assert "Falco" in out


def test_table_with_no_list_raises_user_input_error():
    import pytest

    with pytest.raises(UserInputError, match="no list of records"):
        format_output({"total": 2}, fmt="table")


def test_table_on_a_single_record_raises_user_input_error_not_bare_value_error():
    import pytest

    with pytest.raises(UserInputError, match="try -o json instead"):
        format_output({"name": "Nmap"}, fmt="table")


def test_csv_has_a_header_row_and_one_row_per_item():
    out = format_output(TOOLS_RESPONSE, fmt="csv")
    lines = out.strip().splitlines()
    assert lines[0].split(",") == sorted(["name", "category", "url"])
    assert len(lines) == 3


def test_tsv_uses_tab_delimiter():
    out = format_output(TOOLS_RESPONSE, fmt="tsv")
    assert "\t" in out.splitlines()[0]
    assert "," not in out.splitlines()[0]


def test_limit_truncates_the_item_list():
    out = format_output(TOOLS_RESPONSE, fmt="json", limit=1)
    assert len(json.loads(_plain(out))["tools"]) == 1


def test_limit_only_truncates_the_actual_target_list_when_nested_under_another_key():
    # 'notes' is an unrelated top-level list-of-dicts. The real target list
    # (larger, so extract_items picks it) is nested one level deeper, under
    # a DIFFERENT key ('series' -> 'rows'). Truncating must not touch
    # 'notes' at all, and must actually truncate 'series.rows'.
    data = {
        "notes": [{"a": 1}],
        "series": {"rows": [{"x": 1}, {"x": 2}, {"x": 3}]},
    }
    out = format_output(data, fmt="json", limit=1)
    result = json.loads(_plain(out))
    assert result["notes"] == [{"a": 1}]
    assert result["series"]["rows"] == [{"x": 1}]


def test_short_gives_one_json_line_per_row():
    out = _plain(format_output(TOOLS_RESPONSE, short=True))
    lines = out.strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # each line is valid JSON on its own


def test_short_reorders_name_first():
    out = _plain(format_output(TOOLS_RESPONSE, short=True))
    first_line = out.strip().splitlines()[0]
    assert list(json.loads(first_line).keys())[0] == "name"


def test_search_fields_pulls_matching_values_with_count():
    out = format_output(TOOLS_RESPONSE, search_fields="category")
    result = json.loads(_plain(out))
    assert result["field"] == "category"
    assert result["count"] == 2
    assert sorted(result["values"]) == ["reconnaissance", "runtime-security"]


@given(st.lists(st.dictionaries(st.text(min_size=1, max_size=5), st.integers()), max_size=5))
def test_extract_items_never_crashes_on_arbitrary_lists(items):
    data = {"wrapped": items}
    extract_items(data)  # must not raise, for any list-of-dicts shape


def test_json_output_is_colored_and_stays_valid_json_once_stripped():
    out = format_output({"name": "Nmap", "count": 2, "ok": True, "notes": None}, mode="dark")
    assert "\x1b[" in out  # actually colored, not a no-op
    assert json.loads(click.unstyle(out)) == {
        "name": "Nmap",
        "count": 2,
        "ok": True,
        "notes": None,
    }


def test_json_output_recolors_per_mode():
    dark = format_output({"a": "b"}, mode="dark")
    contrast = format_output({"a": "b"}, mode="contrast")
    assert dark != contrast
    assert click.unstyle(dark) == click.unstyle(contrast)


def test_short_output_is_colored_and_stays_valid_json_once_stripped():
    out = format_output(TOOLS_RESPONSE, short=True, mode="dark")
    assert "\x1b[" in out
    for line in click.unstyle(out).strip().splitlines():
        json.loads(line)
