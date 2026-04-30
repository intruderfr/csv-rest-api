# csv-rest-api

Turn any CSV file into a queryable REST API. Drop CSVs into a directory and they automatically become available as endpoints with filtering, full-text search, sorting, pagination, and field projection — no schema declaration, no database, no boilerplate.

Built for digital transformation: rapidly expose legacy spreadsheet data through a modern API so apps, dashboards, and integrations can consume it without waiting for a database migration project.

## Features

- **Zero-config**: Point it at a folder of CSVs, every file becomes an endpoint at `/api/{filename}`.
- **Auto type-coercion**: Strings, ints, floats, and booleans are parsed automatically.
- **Filtering**: `?department=Engineering`
- **Full-text search**: `?q=alice`
- **Sorting**: `?sort=salary&order=desc`
- **Pagination**: `?page=2&page_size=20`
- **Field projection**: `?fields=name,salary`
- **Single-record fetch**: `/api/employees/3` (uses `id` column or first column)
- **Schema introspection**: `/api/employees/_schema`
- **Hot reload**: Edit a CSV on disk and the change is picked up on the next request.
- **Auto-detected delimiters**: Comma, semicolon, tab, or pipe.

## Install

```bash
git clone https://github.com/intruderfr/csv-rest-api.git
cd csv-rest-api
pip install -r requirements.txt
```

## Usage

```bash
python csv_rest_api.py --data-dir ./examples --port 8080
```

Then in another shell:

```bash
curl http://localhost:8080/
curl http://localhost:8080/api/employees
curl 'http://localhost:8080/api/employees?department=Engineering&sort=salary&order=desc'
curl 'http://localhost:8080/api/employees?q=alice&fields=name,salary'
curl http://localhost:8080/api/employees/2
curl http://localhost:8080/api/employees/_schema
```

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /` | List available datasets and endpoints |
| `GET /api/{name}` | Query a dataset (filters, search, sort, paging, fields) |
| `GET /api/{name}/{id}` | Fetch one row by `id` (or first column) |
| `GET /api/{name}/_schema` | Inferred schema for a dataset |

### Query parameters for `GET /api/{name}`

| Param | Example | Description |
|-------|---------|-------------|
| `q` | `q=alice` | Full-text search across all columns |
| `<column>` | `department=Sales` | Exact-match filter on a column (case-insensitive) |
| `sort` | `sort=salary` | Sort key |
| `order` | `order=desc` | Sort direction (`asc` or `desc`, default `asc`) |
| `page` | `page=2` | Page number, 1-indexed (default `1`) |
| `page_size` | `page_size=20` | Rows per page (default `50`, max `1000`) |
| `fields` | `fields=id,name` | Return only the listed fields |

### Example response

```json
{
  "dataset": "employees",
  "page": 1,
  "page_size": 50,
  "total": 2,
  "data": [
    {"id": 3, "name": "Carol Davis", "department": "Engineering", "salary": 110000, "active": false},
    {"id": 1, "name": "Alice Johnson", "department": "Engineering", "salary": 95000, "active": true}
  ]
}
```

## Examples

Two sample CSVs ship in `examples/`:

- `employees.csv` — staff directory with department, salary, hire date
- `products.csv` — product catalog with prices and stock

## Tests

```bash
pip install pytest
pytest
```

The test suite covers type coercion, filtering, sorting, pagination, projection, and every HTTP route.

## CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--data-dir` | `./data` | Directory of CSV files to serve |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8080` | TCP port |

## Why this exists

Most digital-transformation projects start with a pile of spreadsheets that someone, somewhere, treats as the source of truth. Standing up a "real" database for each one is overkill, and writing bespoke Flask routes per CSV is repetitive. `csv-rest-api` skips both: drop the file in a folder and you have an API. When the data graduates to a real backend, the API contract is already defined.

## License

MIT — see [LICENSE](LICENSE).

## Author

**Aslam Ahamed** — Head of IT @ Prestige One Developments, Dubai
LinkedIn: <https://www.linkedin.com/in/aslam-ahamed/>
