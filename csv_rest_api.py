#!/usr/bin/env python3
"""csv-rest-api: Turn any CSV file into a queryable REST API.

Drop CSV files into a directory and they automatically become available as
REST endpoints with filtering, pagination, search, sort, and field projection.

Usage:
    python csv_rest_api.py --data-dir ./examples --port 8080

Author: Aslam Ahamed (Head of IT @ Prestige One Developments, Dubai)
License: MIT
"""
from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("csv-rest-api")


def coerce_value(value: Any) -> Any:
    """Coerce a string value to int, float, bool, or None when sensible.

    Empty strings become None. "true"/"false" (any case) become booleans.
    Otherwise we try int, then float, then keep the string.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped == "":
        return None
    lower = stripped.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return stripped


def coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    """Apply coerce_value to every column in a row."""
    return {k: coerce_value(v) for k, v in row.items()}


def load_csv(path: Path) -> list[dict[str, Any]]:
    """Load a CSV file as a list of dicts. Auto-detects the delimiter."""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        return [coerce_row(r) for r in reader]


RESERVED_PARAMS = {"q", "page", "page_size", "sort", "order", "fields"}


def filter_rows(rows: list[dict[str, Any]], params: dict[str, str]) -> list[dict[str, Any]]:
    """Apply ?col=value exact filters and ?q=text full-text search."""
    out = rows
    needle = params.get("q")
    if needle:
        lowered = needle.lower()
        out = [r for r in out if any(lowered in str(v).lower() for v in r.values() if v is not None)]
    for key, val in params.items():
        if key in RESERVED_PARAMS:
            continue
        out = [r for r in out if str(r.get(key, "")).lower() == val.lower()]
    return out


def sort_rows(rows: list[dict[str, Any]], sort: str | None, order: str) -> list[dict[str, Any]]:
    """Sort rows by a column, putting None values last regardless of direction."""
    if not sort:
        return rows
    reverse = order.lower() == "desc"

    def key(row: dict[str, Any]):
        v = row.get(sort)
        return (v is None, v if v is not None else "")

    return sorted(rows, key=key, reverse=reverse)


def paginate(rows: list[dict[str, Any]], page: int, page_size: int) -> list[dict[str, Any]]:
    """Slice rows for the requested page (1-indexed)."""
    start = (max(page, 1) - 1) * page_size
    return rows[start : start + page_size]


def project_fields(rows: list[dict[str, Any]], fields: str | None) -> list[dict[str, Any]]:
    """Return only the comma-separated list of fields, if requested."""
    if not fields:
        return rows
    keep = [f.strip() for f in fields.split(",") if f.strip()]
    return [{k: r.get(k) for k in keep} for r in rows]


def create_app(data_dir: Path) -> Flask:
    """Build a Flask app that serves every CSV in data_dir as /api/<filename>."""
    app = Flask(__name__)
    cache: dict[str, list[dict[str, Any]]] = {}
    mtimes: dict[str, float] = {}

    def get_dataset(name: str) -> list[dict[str, Any]]:
        path = data_dir / f"{name}.csv"
        if not path.is_file():
            abort(404, description=f"Dataset '{name}' not found")
        mtime = path.stat().st_mtime
        if name not in cache or mtimes.get(name) != mtime:
            log.info("Loading %s", path)
            cache[name] = load_csv(path)
            mtimes[name] = mtime
        return cache[name]

    @app.get("/")
    def index():
        files = sorted(p.stem for p in data_dir.glob("*.csv"))
        return jsonify(
            {
                "service": "csv-rest-api",
                "data_dir": str(data_dir),
                "datasets": files,
                "endpoints": [f"/api/{f}" for f in files],
            }
        )

    @app.get("/api/<name>/_schema")
    def schema(name: str):
        rows = get_dataset(name)
        if not rows:
            return jsonify({"dataset": name, "fields": {}, "row_count": 0})
        types: dict[str, str] = {}
        for row in rows:
            for k, v in row.items():
                if v is not None and k not in types:
                    types[k] = type(v).__name__
        for k in rows[0].keys():
            types.setdefault(k, "NoneType")
        return jsonify({"dataset": name, "fields": types, "row_count": len(rows)})

    @app.get("/api/<name>")
    def list_dataset(name: str):
        rows = get_dataset(name)
        params = request.args.to_dict()
        try:
            page = int(params.get("page", 1))
            page_size = min(int(params.get("page_size", 50)), 1000)
        except ValueError:
            abort(400, description="page and page_size must be integers")
        sort = params.get("sort")
        order = params.get("order", "asc")
        fields = params.get("fields")
        filtered = filter_rows(rows, params)
        sorted_rows = sort_rows(filtered, sort, order)
        paged = paginate(sorted_rows, page, page_size)
        projected = project_fields(paged, fields)
        return jsonify(
            {
                "dataset": name,
                "page": page,
                "page_size": page_size,
                "total": len(filtered),
                "data": projected,
            }
        )

    @app.get("/api/<name>/<row_id>")
    def get_one(name: str, row_id: str):
        rows = get_dataset(name)
        if not rows:
            abort(404)
        first_col = next(iter(rows[0].keys()))
        id_field = "id" if "id" in rows[0] else first_col
        for r in rows:
            if str(r.get(id_field)) == row_id:
                return jsonify(r)
        abort(404, description=f"No row with {id_field}={row_id}")

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": getattr(e, "description", "Bad request")}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": getattr(e, "description", "Not found")}), 404

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("./data"),
                        help="Directory containing CSV files")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    args.data_dir = args.data_dir.resolve()
    if not args.data_dir.is_dir():
        raise SystemExit(f"Data directory does not exist: {args.data_dir}")
    app = create_app(args.data_dir)
    log.info("Serving CSVs from %s on http://%s:%d", args.data_dir, args.host, args.port)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
