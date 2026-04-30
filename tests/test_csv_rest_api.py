"""Tests for csv-rest-api."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csv_rest_api import (  # noqa: E402
    coerce_row,
    coerce_value,
    create_app,
    filter_rows,
    load_csv,
    paginate,
    project_fields,
    sort_rows,
)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    (tmp_path / "employees.csv").write_text(
        "id,name,department,salary,active\n"
        "1,Alice,Engineering,95000,true\n"
        "2,Bob,Sales,72000,true\n"
        "3,Carol,Engineering,110000,false\n"
        "4,David,Marketing,68000,true\n",
        encoding="utf-8",
    )
    (tmp_path / "products.csv").write_text(
        "sku,name,price\nP001,Mouse,29.99\nP002,Keyboard,89.99\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def client(data_dir: Path):
    return create_app(data_dir).test_client()


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def test_coerce_value_handles_all_types():
    assert coerce_value("1") == 1
    assert coerce_value("1.5") == 1.5
    assert coerce_value("true") is True
    assert coerce_value("False") is False
    assert coerce_value("") is None
    assert coerce_value("hello") == "hello"
    assert coerce_value(None) is None
    assert coerce_value(42) == 42


def test_coerce_row_applies_to_every_column():
    out = coerce_row({"id": "7", "name": "X", "active": "false", "blank": ""})
    assert out == {"id": 7, "name": "X", "active": False, "blank": None}


def test_load_csv_roundtrip(data_dir: Path):
    rows = load_csv(data_dir / "employees.csv")
    assert len(rows) == 4
    assert rows[0]["name"] == "Alice"
    assert rows[0]["salary"] == 95000
    assert rows[2]["active"] is False


def test_filter_rows_exact_match():
    rows = [{"d": "Eng"}, {"d": "Sales"}, {"d": "Eng"}]
    out = filter_rows(rows, {"d": "Eng"})
    assert len(out) == 2


def test_filter_rows_full_text_search():
    rows = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Alicia"}]
    out = filter_rows(rows, {"q": "ali"})
    assert len(out) == 2


def test_filter_rows_ignores_reserved_params():
    rows = [{"d": "Eng"}, {"d": "Sales"}]
    # 'page' is reserved — should not be treated as a column filter
    out = filter_rows(rows, {"page": "1"})
    assert len(out) == 2


def test_sort_rows_asc_and_desc():
    rows = [{"x": 3}, {"x": 1}, {"x": 2}]
    asc = sort_rows(rows, "x", "asc")
    desc = sort_rows(rows, "x", "desc")
    assert [r["x"] for r in asc] == [1, 2, 3]
    assert [r["x"] for r in desc] == [3, 2, 1]


def test_sort_rows_nulls_last():
    rows = [{"x": 2}, {"x": None}, {"x": 1}]
    out = sort_rows(rows, "x", "asc")
    assert [r["x"] for r in out] == [1, 2, None]


def test_paginate_slices_correctly():
    rows = [{"i": i} for i in range(10)]
    assert paginate(rows, 1, 3) == [{"i": 0}, {"i": 1}, {"i": 2}]
    assert paginate(rows, 4, 3) == [{"i": 9}]
    assert paginate(rows, 99, 3) == []


def test_project_fields_keeps_only_requested():
    rows = [{"a": 1, "b": 2, "c": 3}]
    assert project_fields(rows, "a,c") == [{"a": 1, "c": 3}]
    assert project_fields(rows, None) == rows


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------


def test_index_lists_datasets(client):
    body = client.get("/").get_json()
    assert "employees" in body["datasets"]
    assert "products" in body["datasets"]
    assert "/api/employees" in body["endpoints"]


def test_list_dataset_returns_all_rows(client):
    body = client.get("/api/employees").get_json()
    assert body["total"] == 4
    assert body["data"][0]["name"] == "Alice"


def test_filter_by_column(client):
    body = client.get("/api/employees?department=Engineering").get_json()
    assert body["total"] == 2
    assert all(r["department"] == "Engineering" for r in body["data"])


def test_full_text_search(client):
    body = client.get("/api/employees?q=carol").get_json()
    assert body["total"] == 1
    assert body["data"][0]["name"] == "Carol"


def test_sort_descending_by_salary(client):
    body = client.get("/api/employees?sort=salary&order=desc").get_json()
    salaries = [r["salary"] for r in body["data"]]
    assert salaries == sorted(salaries, reverse=True)


def test_pagination(client):
    body = client.get("/api/employees?page=1&page_size=2").get_json()
    assert len(body["data"]) == 2
    assert body["total"] == 4
    page2 = client.get("/api/employees?page=2&page_size=2").get_json()
    assert len(page2["data"]) == 2


def test_field_projection(client):
    body = client.get("/api/employees?fields=name,salary").get_json()
    assert all(set(r.keys()) == {"name", "salary"} for r in body["data"])


def test_get_one_by_id(client):
    body = client.get("/api/employees/2").get_json()
    assert body["name"] == "Bob"


def test_get_one_by_first_column_when_no_id(client):
    body = client.get("/api/products/P001").get_json()
    assert body["name"] == "Mouse"


def test_get_one_returns_404_for_missing(client):
    resp = client.get("/api/employees/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_schema_endpoint(client):
    body = client.get("/api/employees/_schema").get_json()
    assert body["row_count"] == 4
    assert body["fields"]["salary"] == "int"
    assert body["fields"]["active"] == "bool"


def test_unknown_dataset_404(client):
    resp = client.get("/api/nonexistent")
    assert resp.status_code == 404


def test_invalid_page_returns_400(client):
    resp = client.get("/api/employees?page=abc")
    assert resp.status_code == 400
