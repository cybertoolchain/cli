# tests/test_output.py
from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from toolchain.output import extract_items, format_output

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
    assert json.loads(out) == TOOLS_RESPONSE


def test_json_output_is_indented():
    out = format_output({"a": 1}, fmt="json")
    assert out == '{\n  "a": 1\n}'


def test_table_renders_a_grid_with_headers():
    out = format_output(TOOLS_RESPONSE, fmt="table")
    assert "name" in out
    assert "Nmap" in out
    assert "Falco" in out


def test_table_with_no_list_raises_value_error():
    import pytest

    with pytest.raises(ValueError, match="no list of records"):
        format_output({"total": 2}, fmt="table")


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
    assert len(json.loads(out)["tools"]) == 1


def test_short_gives_one_json_line_per_row():
    out = format_output(TOOLS_RESPONSE, short=True)
    lines = out.strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # each line is valid JSON on its own


def test_short_reorders_name_first():
    out = format_output(TOOLS_RESPONSE, short=True)
    first_line = out.strip().splitlines()[0]
    assert list(json.loads(first_line).keys())[0] == "name"


def test_search_fields_pulls_matching_values_with_count():
    out = format_output(TOOLS_RESPONSE, search_fields="category")
    result = json.loads(out)
    assert result["field"] == "category"
    assert result["count"] == 2
    assert sorted(result["values"]) == ["reconnaissance", "runtime-security"]


@given(st.lists(st.dictionaries(st.text(min_size=1, max_size=5), st.integers()), max_size=5))
def test_extract_items_never_crashes_on_arbitrary_lists(items):
    data = {"wrapped": items}
    extract_items(data)  # must not raise, for any list-of-dicts shape
