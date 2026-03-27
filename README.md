# CSV/JSON Converter API

A Django REST Framework project that provides APIs to convert data between CSV and JSON formats. Includes both raw content APIs and file upload APIs with a powerful transformation rules engine. Built with a pluggable mapping registry pattern for easy extensibility.

## Quick Start

### Prerequisites

- Docker and Docker Compose

### Run the Server

```bash
cd csv_json_converter
docker compose up -d
docker compose exec web python manage.py migrate
```

The API will be available at **http://localhost:8001**.

To view logs:

```bash
docker compose logs -f
```

To stop:

```bash
docker compose down
```

### Run without Docker (Local Development)

```bash
cd csv_json_converter
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8001
```

The API will be available at **http://localhost:8001**.

## Project Structure

```
csv_json_converter/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── manage.py
├── converter/                      # Django project settings
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/mapping/                   # Mapping app
│   ├── apps.py
│   ├── models.py                   # ConversionJob model
│   ├── registry.py                 # Mapping function registry
│   ├── rules.py                    # Transformation rules engine
│   ├── serializers.py              # DRF serializers
│   ├── views.py                    # Raw content API views
│   ├── views_file.py               # File upload API views
│   ├── urls.py
│   ├── maps/                       # Mapper functions
│   │   ├── csv_to_json.py          # Raw content CSV->JSON
│   │   ├── json_to_csv.py          # Raw content JSON->CSV
│   │   ├── csv_to_json_file.py     # File-based CSV->JSON with rules
│   │   └── json_to_csv_file.py     # File-based JSON->CSV with rules
│   └── utils/
│       └── loader.py               # Registry lookup helper
├── media/                          # Uploaded and converted files
│   └── conversions/<job_id>/
│       ├── input/                  # Original uploaded files
│       └── output/                 # Converted output files
└── test_data/                      # Test files and Postman collection
    ├── employees.csv
    ├── products.csv
    ├── orders_semicolon.csv
    ├── sample.json
    └── CSV_JSON_Converter.postman_collection.json
```

## API Endpoints

### Raw Content APIs (JSON body)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mapping/registry/` | List all available mapping functions |
| `POST` | `/api/mapping/csv-to-json/` | Convert CSV string to JSON |
| `POST` | `/api/mapping/json-to-csv/` | Convert JSON string to CSV |
| `POST` | `/api/mapping/convert/` | Generic conversion (specify mapper by name) |

### File Upload APIs (multipart/form-data)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mapping/file/csv-to-json/` | Upload CSV file, convert to JSON with rules |
| `POST` | `/api/mapping/file/json-to-csv/` | Upload JSON file, convert to CSV with rules |

### Job Management APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mapping/file/jobs/` | List all conversion jobs |
| `GET` | `/api/mapping/file/jobs/<job_id>/` | Get job detail with logs and rules |
| `GET` | `/api/mapping/file/jobs/<job_id>/download/` | Download the converted output file |

---

## Raw Content APIs

### 1. List Mapping Registry

```
GET /api/mapping/registry/
```

**Query Parameters:** `?search=csv` (optional, case-insensitive filter)

```bash
curl http://localhost:8001/api/mapping/registry/
```

```json
[
  { "id": 1, "name": "csv_to_json", "description": "Convert CSV string content to a JSON array of objects." },
  { "id": 2, "name": "json_to_csv", "description": "Convert a JSON array of objects to CSV string." },
  { "id": 3, "name": "csv_to_json_file", "description": "Convert CSV content to JSON with optional transformation rules." },
  { "id": 4, "name": "json_to_csv_file", "description": "Convert JSON content to CSV with optional transformation rules." }
]
```

### 2. CSV to JSON (raw content)

```
POST /api/mapping/csv-to-json/
Content-Type: application/json
```

**Request Payload:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | Yes | — | Raw CSV string |
| `delimiter` | string | No | auto-detect | Delimiter (`,`, `\t`, `;`, `\|`) |
| `quotechar` | string | No | `"` | Quote character |

```bash
curl -X POST http://localhost:8001/api/mapping/csv-to-json/ \
  -H "Content-Type: application/json" \
  -d '{"content": "name,age,city\nAlice,30,New York\nBob,25,London"}'
```

**Response** `200 OK`

```json
{
  "output": "[\n  {\n    \"name\": \"Alice\",\n    \"age\": \"30\",\n    \"city\": \"New York\"\n  },\n  {\n    \"name\": \"Bob\",\n    \"age\": \"25\",\n    \"city\": \"London\"\n  }\n]",
  "logs": [
    "Auto-detected delimiter: ','",
    "Parsed 2 row(s) with 3 column(s)",
    "Columns: name, age, city"
  ],
  "output_type": "JSON"
}
```

**Error Response** `400 Bad Request`

```json
{
  "error": "Conversion failed",
  "details": "CSV content is empty"
}
```

### 3. JSON to CSV (raw content)

```
POST /api/mapping/json-to-csv/
Content-Type: application/json
```

**Request Payload:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | Yes | — | JSON string (array of objects or single object) |
| `delimiter` | string | No | `,` | CSV delimiter |
| `quotechar` | string | No | `"` | Quote character |
| `columns` | array | No | all keys | Explicit column order |
| `quote_header` | boolean | No | `false` | Quote header row |
| `quote_data` | boolean | No | `true` | Quote data fields |

```bash
curl -X POST http://localhost:8001/api/mapping/json-to-csv/ \
  -H "Content-Type: application/json" \
  -d '{"content": "[{\"name\":\"Alice\",\"age\":30}]", "quote_data": false}'
```

**Response** `200 OK`

```json
{
  "output": "name,age\nAlice,30\n",
  "logs": [
    "Converting 1 row(s) with 2 column(s)",
    "Columns: name, age"
  ],
  "output_type": "CSV"
}
```

**Error Response** `400 Bad Request`

```json
{
  "error": "Conversion failed",
  "details": "Expected a JSON array of objects, got str"
}
```

### 4. Generic Convert

```
POST /api/mapping/convert/
Content-Type: application/json
```

**Request Payload:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mapping_function` | string | Yes | Registry key (e.g., `csv_to_json`, `json_to_csv`) |
| `content` | string | Yes | Raw content to convert |
| *...other fields* | — | No | Passed through as kwargs to the mapper function |

```bash
curl -X POST http://localhost:8001/api/mapping/convert/ \
  -H "Content-Type: application/json" \
  -d '{"mapping_function": "csv_to_json", "content": "name,age\nAlice,30"}'
```

**Response** `200 OK`

```json
{
  "output": "[\n  {\n    \"name\": \"Alice\",\n    \"age\": \"30\"\n  }\n]",
  "logs": [
    "Auto-detected delimiter: ','",
    "Parsed 1 row(s) with 2 column(s)",
    "Columns: name, age"
  ],
  "output_type": "JSON"
}
```

**Error Response — unknown mapper** `400 Bad Request`

```json
{
  "error": "Unknown mapping function 'nonexistent'",
  "available": "csv_to_json, csv_to_json_file, json_to_csv, json_to_csv_file"
}
```

**Error Response — missing fields** `400 Bad Request`

```json
{
  "error": "mapping_function is required"
}
```

---

## File Upload APIs with Rules

These endpoints accept file uploads via `multipart/form-data`, apply transformation rules, save both input and output files to disk, and track the conversion as a job.

### 5. Upload CSV -> JSON

```
POST /api/mapping/file/csv-to-json/
Content-Type: multipart/form-data
```

**Request Payload (form-data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | CSV file (.csv, .tsv, .txt) |
| `rules` | text (JSON) | No | Transformation rules JSON string |

**Example — No rules:**

```bash
curl -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/employees.csv"
```

**Example — With rules (filter + rename + transform):**

```bash
curl -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/employees.csv" \
  -F 'rules={
    "filter_rules": {"department": "Engineering"},
    "column_mapping": {"first_name": "FirstName", "last_name": "LastName"},
    "include_columns": ["FirstName", "LastName", "email", "salary"],
    "transforms": {"FirstName": "uppercase", "email": "lowercase"},
    "column_order": ["FirstName", "LastName", "email", "salary"]
  }'
```

**Response** `201 Created`

```json
{
  "job_id": "f27d9b46-56df-4a1a-8027-ebd64d48f98c",
  "status": "completed",
  "direction": "csv_to_json",
  "input_filename": "employees.csv",
  "output_filename": "employees.json",
  "rows_processed": 4,
  "columns_count": 4,
  "rules_applied": { ... },
  "logs": [
    "Auto-detected delimiter: ','",
    "Parsed 10 row(s) with 8 column(s)",
    "Rule [filter]: 10 -> 4 rows (filter: {'department': 'Engineering'})",
    "Rule [column_mapping]: Renamed 2 column(s)",
    "Rule [include_columns]: Keeping 4 column(s)",
    "Rule [transforms]: Applied transforms: {'FirstName': 'uppercase', 'email': 'lowercase'}",
    "Output: 4 row(s) with 4 column(s)"
  ],
  "output": "[...json content...]",
  "download_url": "http://localhost:8001/api/mapping/file/jobs/f27d9b46-.../download/"
}
```

**Error Response — invalid file type** `400 Bad Request`

```json
{
  "error": "Invalid file type '.pdf'. Expected .csv, .tsv, or .txt"
}
```

**Error Response — no file** `400 Bad Request`

```json
{
  "error": "No file uploaded. Send a CSV file in the 'file' field."
}
```

**Error Response — conversion failure** `400 Bad Request`

```json
{
  "job_id": "a1b2c3d4-...",
  "error": "Conversion failed",
  "details": "CSV content has headers but no data rows"
}
```

### 6. Upload JSON -> CSV

```
POST /api/mapping/file/json-to-csv/
Content-Type: multipart/form-data
```

**Request Payload (form-data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | JSON file (.json) |
| `rules` | text (JSON) | No | Transformation rules JSON string |

**Example — No rules:**

```bash
curl -X POST http://localhost:8001/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json"
```

**Example — With rules:**

```bash
curl -X POST http://localhost:8001/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json" \
  -F 'rules={
    "column_mapping": {"name": "Product Name", "brand": "Brand", "price": "Price (USD)"},
    "exclude_columns": ["id"],
    "transforms": {"Brand": "uppercase"},
    "column_order": ["Product Name", "Brand", "Price (USD)", "in_stock"],
    "delimiter": ";",
    "quote_data": false
  }'
```

**Response** `201 Created`

```json
{
  "job_id": "71f94324-75ca-4f22-a2c1-6cd1955fbef1",
  "status": "completed",
  "direction": "json_to_csv",
  "input_filename": "sample.json",
  "output_filename": "sample.csv",
  "rows_processed": 5,
  "columns_count": 4,
  "rules_applied": {
    "column_mapping": {"name": "Product Name", "brand": "Brand", "price": "Price (USD)"},
    "exclude_columns": ["id"],
    "transforms": {"Brand": "uppercase"},
    "column_order": ["Product Name", "Brand", "Price (USD)", "in_stock"],
    "delimiter": ";",
    "quote_data": false
  },
  "logs": [
    "Parsed 5 row(s) with 5 column(s)",
    "Input columns: id, name, brand, price, in_stock",
    "Rule [column_mapping]: Renamed 3 column(s): {'name': 'Product Name', 'brand': 'Brand', 'price': 'Price (USD)'}",
    "Rule [exclude_columns]: Dropping column(s): ['id']",
    "Rule [transforms]: Applied transforms: {'Brand': 'uppercase'}",
    "Rule [column_order]: Output order: ['Product Name', 'Brand', 'Price (USD)', 'in_stock']",
    "Output: 5 row(s) with 4 column(s)",
    "Output columns: Product Name, Brand, Price (USD), in_stock"
  ],
  "output": "Product Name;Brand;Price (USD);in_stock\nLaptop Pro;TECHBRAND;1299.99;True\n...",
  "download_url": "http://localhost:8001/api/mapping/file/jobs/71f94324-.../download/"
}
```

**Error Response** `400 Bad Request`

```json
{
  "job_id": "a1b2c3d4-...",
  "error": "Conversion failed",
  "details": "JSON content is empty"
}
```

---

## Transformation Rules Reference

Rules are passed as a JSON string in the `rules` field of file upload endpoints. All rules are optional and applied in the order listed below.

| Rule | Type | Example | Description |
|------|------|---------|-------------|
| `filter_rules` | `{"col": "val"}` | `{"department": "Engineering"}` | Keep only rows where column equals value (case-insensitive) |
| `column_mapping` | `{"old": "new"}` | `{"first_name": "FirstName"}` | Rename columns |
| `include_columns` | `["col1", "col2"]` | `["name", "email"]` | Keep only these columns (drop all others) |
| `exclude_columns` | `["col"]` | `["id", "internal_code"]` | Drop these specific columns |
| `default_values` | `{"col": "val"}` | `{"status": "N/A"}` | Fill missing or empty values with defaults |
| `transforms` | `{"col": "type"}` | `{"name": "uppercase"}` | Transform values per column |
| `column_order` | `["col2", "col1"]` | `["name", "age", "city"]` | Reorder output columns |
| `delimiter` | `string` | `";"` | CSV delimiter (JSON->CSV only) |
| `quotechar` | `string` | `"'"` | Quote character |
| `quote_header` | `boolean` | `false` | Quote CSV header row |
| `quote_data` | `boolean` | `true` | Quote CSV data fields |

### Transform Types

| Type | Effect | Example |
|------|--------|---------|
| `uppercase` | Convert to UPPER CASE | `alice` -> `ALICE` |
| `lowercase` | Convert to lower case | `ALICE` -> `alice` |
| `title` | Convert to Title Case | `alice johnson` -> `Alice Johnson` |
| `trim` | Strip leading/trailing whitespace | `" alice "` -> `"alice"` |
| `strip` | Same as trim | `" alice "` -> `"alice"` |

### Rules Processing Order

Rules are applied in this fixed sequence (see `apps/mapping/rules.py`):

| Step | Rule | Uses column names | What happens |
|------|------|-------------------|-------------|
| 1 | `filter_rules` | **Original** | Rows are filtered first, reducing data before any other operation |
| 2 | `column_mapping` | **Original → New** | Columns are renamed — all subsequent rules must use the **new** names |
| 3 | `include_columns` | **New** (after rename) | Only listed columns are kept, everything else is dropped |
| 4 | `exclude_columns` | **New** (after rename) | Listed columns are dropped |
| 5 | `default_values` | **New** (after rename) | Missing or empty values are filled with defaults |
| 6 | `transforms` | **New** (after rename) | Value transformations are applied per column |
| 7 | `column_order` | **New** (after rename) | Output columns are reordered |

> **Key detail:** The order matters because renaming happens at step 2. Rules in steps 3–7 must reference the **new** column names (e.g., `"FirstName"`, not `"first_name"`). Only `filter_rules` (step 1) uses the **original** column names since it runs before the rename.

### How Rules Flow Through the Code

1. **Frontend** — User configures rules in the sidebar (JSON text inputs). The **Rules Payload** preview shows the live JSON that will be sent.
2. **Request** — Rules are sent as a JSON string in the `rules` form field alongside the uploaded file (`multipart/form-data`).
3. **View** (`views_file.py`) — Parses the rules JSON string and passes it to the mapper function.
4. **Mapper** (`csv_to_json_file.py` / `json_to_csv_file.py`) — Parses the file content into a list of row dicts, then calls `apply_rules(rows, rules, logs)`.
5. **Rules Engine** (`rules.py`) — Applies each rule in order, mutating the row list and appending log messages.
6. **Response** — Returns the converted output, processing logs, row/column counts, and a download URL.

### Example: Combining Multiple Rules

Given `employees.csv` with 10 rows and 8 columns:

```json
{
  "filter_rules": {"department": "Engineering"},
  "column_mapping": {"first_name": "FirstName", "salary": "AnnualPay"},
  "include_columns": ["FirstName", "email", "AnnualPay"],
  "transforms": {"FirstName": "uppercase", "email": "lowercase"},
  "default_values": {"AnnualPay": "0"},
  "column_order": ["FirstName", "email", "AnnualPay"]
}
```

**Step-by-step processing:**

| Step | Rule | Before | After |
|------|------|--------|-------|
| 1 | `filter_rules` | 10 rows, 8 columns | 4 rows (only `department = "Engineering"`), 8 columns |
| 2 | `column_mapping` | columns: `first_name`, `salary`, ... | columns: `FirstName`, `AnnualPay`, ... |
| 3 | `include_columns` | 8 columns | 3 columns: `FirstName`, `email`, `AnnualPay` |
| 4 | `transforms` | `FirstName: "alice"`, `email: "Alice@Co.COM"` | `FirstName: "ALICE"`, `email: "alice@co.com"` |
| 5 | `default_values` | `AnnualPay: ""` (empty) | `AnnualPay: "0"` |
| 6 | `column_order` | order: `FirstName, email, AnnualPay` | same (already in desired order) |

**Result:** 4 rows, 3 columns — Engineering employees with uppercased names, lowercased emails, and default pay values filled in.

**Processing logs returned:**
```
Auto-detected delimiter: ','
Parsed 10 row(s) with 8 column(s)
Rule [filter]: 10 -> 4 rows (filter: {'department': 'Engineering'})
Rule [column_mapping]: Renamed 2 column(s)
Rule [include_columns]: Keeping 3 column(s)
Rule [transforms]: Applied transforms: {'FirstName': 'uppercase', 'email': 'lowercase'}
Rule [default_values]: Applied defaults for: ['AnnualPay']
Rule [column_order]: Output order: ['FirstName', 'email', 'AnnualPay']
Output: 4 row(s) with 3 column(s)
```

---

## Job Management APIs

### 7. List All Jobs

```
GET /api/mapping/file/jobs/
```

**Query Parameters:**

| Parameter | Values | Description |
|-----------|--------|-------------|
| `status` | `pending`, `processing`, `completed`, `failed` | Filter by job status |
| `direction` | `csv_to_json`, `json_to_csv` | Filter by conversion direction |

```bash
curl http://localhost:8001/api/mapping/file/jobs/?status=completed
```

```json
{
  "count": 3,
  "results": [
    {
      "job_id": "f27d9b46-...",
      "direction": "csv_to_json",
      "status": "completed",
      "input_filename": "employees.csv",
      "output_filename": "employees.json",
      "rows_processed": 10,
      "columns_count": 8,
      "rules": {},
      "created_at": "2026-03-18T05:53:05.000Z",
      "completed_at": "2026-03-18T05:53:05.100Z",
      "download_url": "http://localhost:8001/api/mapping/file/jobs/f27d9b46-.../download/"
    }
  ]
}
```

### 8. Get Job Detail

```
GET /api/mapping/file/jobs/<job_id>/
```

Returns full job details including logs, rules applied, and error messages.

```bash
curl http://localhost:8001/api/mapping/file/jobs/f27d9b46-56df-4a1a-8027-ebd64d48f98c/
```

**Response** `200 OK`

```json
{
  "job_id": "f27d9b46-56df-4a1a-8027-ebd64d48f98c",
  "direction": "csv_to_json",
  "status": "completed",
  "input_filename": "employees.csv",
  "output_filename": "employees.json",
  "rows_processed": 4,
  "columns_count": 4,
  "rules": {
    "filter_rules": {"department": "Engineering"},
    "column_mapping": {"first_name": "FirstName", "last_name": "LastName"},
    "include_columns": ["FirstName", "LastName", "email", "salary"],
    "transforms": {"FirstName": "uppercase", "email": "lowercase"},
    "column_order": ["FirstName", "LastName", "email", "salary"]
  },
  "logs": "Auto-detected delimiter: ','\nParsed 10 row(s) with 8 column(s)\nRule [filter]: 10 -> 4 rows ...",
  "error_message": "",
  "created_at": "2026-03-18T05:53:05.000000+00:00",
  "completed_at": "2026-03-18T05:53:05.100000+00:00",
  "download_url": "http://localhost:8001/api/mapping/file/jobs/f27d9b46-.../download/"
}
```

**Error Response** `404 Not Found` — when `job_id` does not exist.

### 9. Download Output File

```
GET /api/mapping/file/jobs/<job_id>/download/
```

Downloads the converted output file as an attachment. Only works for completed jobs.

```bash
curl -o output.json http://localhost:8001/api/mapping/file/jobs/f27d9b46-.../download/
```

**Success Response:** Binary file download with `Content-Disposition: attachment; filename="<output_filename>"`

**Error Response** `400 Bad Request` — job not yet completed:

```json
{
  "error": "Job is not completed (status: processing)"
}
```

**Error Response** `404 Not Found` — no output file available:

```json
{
  "error": "No output file available for this job"
}
```

In Postman, use **Send and Download** to save the file.

---

## Response Formats

### Raw Content API Success (200)

```json
{
  "output": "...converted content...",
  "logs": ["Parsed 3 row(s) with 3 column(s)"],
  "output_type": "JSON"
}
```

### File Upload API Success (201)

```json
{
  "job_id": "uuid",
  "status": "completed",
  "direction": "csv_to_json",
  "input_filename": "data.csv",
  "output_filename": "data.json",
  "rows_processed": 10,
  "columns_count": 5,
  "rules_applied": { ... },
  "logs": ["..."],
  "output": "...converted content...",
  "download_url": "http://localhost:8001/api/mapping/file/jobs/<id>/download/"
}
```

### Error Response (400/500)

```json
{
  "error": "Conversion failed",
  "details": "CSV content is empty"
}
```

---

## Testing with curl (Step-by-Step)

A complete walkthrough to test every endpoint using curl and the included test data files.

### Step 1: Start the Server

```bash
docker compose up -d
docker compose exec web python manage.py migrate
```

Verify the server is running:

```bash
curl http://localhost:8001/api/mapping/registry/
```

You should see a JSON array of 4 mapping functions.

### Step 2: Test Raw Content — CSV to JSON

**Basic CSV (auto-detect comma delimiter):**

```bash
curl -s -X POST http://localhost:8001/api/mapping/csv-to-json/ \
  -H "Content-Type: application/json" \
  -d '{"content": "name,age,city\nAlice,30,New York\nBob,25,London\nCharlie,35,Tokyo"}'
```

Expected: `output_type: "JSON"` with 3 rows, 3 columns.

**Semicolon delimiter (auto-detect):**

```bash
curl -s -X POST http://localhost:8001/api/mapping/csv-to-json/ \
  -H "Content-Type: application/json" \
  -d '{"content": "order_id;customer;product;quantity\nORD-001;Acme Corp;Widget A;50\nORD-002;Globex Inc;Gadget B;25"}'
```

Expected: logs show `Auto-detected delimiter: ';'`.

**Tab delimiter (explicit):**

```bash
curl -s -X POST http://localhost:8001/api/mapping/csv-to-json/ \
  -H "Content-Type: application/json" \
  -d '{"content": "id\tname\tvalue\n1\tAlpha\t100\n2\tBeta\t200", "delimiter": "\t"}'
```

**Error case — empty content:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/csv-to-json/ \
  -H "Content-Type: application/json" \
  -d '{"content": ""}'
```

Expected: `400` with `"details": "CSV content is empty"`.

### Step 3: Test Raw Content — JSON to CSV

**Basic JSON array:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/json-to-csv/ \
  -H "Content-Type: application/json" \
  -d '{"content": "[{\"name\":\"Alice\",\"age\":30,\"city\":\"New York\"},{\"name\":\"Bob\",\"age\":25,\"city\":\"London\"}]"}'
```

Expected: CSV output with quoted data fields.

**Single JSON object (auto-wrapped):**

```bash
curl -s -X POST http://localhost:8001/api/mapping/json-to-csv/ \
  -H "Content-Type: application/json" \
  -d '{"content": "{\"name\":\"Alice\",\"age\":30,\"city\":\"New York\"}"}'
```

Expected: logs include `"Input was a single JSON object, wrapped into an array"`.

**Custom column order + no quotes:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/json-to-csv/ \
  -H "Content-Type: application/json" \
  -d '{"content": "[{\"name\":\"Alice\",\"age\":30,\"city\":\"New York\"}]", "columns": ["city", "name", "age"], "quote_data": false}'
```

Expected: column order is `city,name,age`.

**Semicolon delimiter:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/json-to-csv/ \
  -H "Content-Type: application/json" \
  -d '{"content": "[{\"a\":1,\"b\":2},{\"a\":3,\"b\":4}]", "delimiter": ";"}'
```

**Error case — invalid JSON:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/json-to-csv/ \
  -H "Content-Type: application/json" \
  -d '{"content": "this is not valid json"}'
```

Expected: `400` with JSON decode error details.

### Step 4: Test Generic Convert Endpoint

**CSV to JSON via generic endpoint:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/convert/ \
  -H "Content-Type: application/json" \
  -d '{"mapping_function": "csv_to_json", "content": "name,age\nAlice,30\nBob,25"}'
```

**JSON to CSV with extra options via generic endpoint:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/convert/ \
  -H "Content-Type: application/json" \
  -d '{"mapping_function": "json_to_csv", "content": "[{\"x\":1,\"y\":2},{\"x\":3,\"y\":4}]", "delimiter": ";", "quote_data": false}'
```

**Error case — unknown mapper:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/convert/ \
  -H "Content-Type: application/json" \
  -d '{"mapping_function": "nonexistent", "content": "test"}'
```

Expected: `400` with list of available mapping functions.

### Step 5: Test File Upload — CSV to JSON

**Upload with no rules:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/employees.csv"
```

Expected: `201` with 10 rows, 8 columns.

**Upload with filter + rename + transform rules:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/employees.csv" \
  -F 'rules={
    "filter_rules": {"department": "Engineering"},
    "column_mapping": {"first_name": "FirstName", "last_name": "LastName"},
    "include_columns": ["FirstName", "LastName", "email", "salary"],
    "transforms": {"FirstName": "uppercase", "email": "lowercase"},
    "column_order": ["FirstName", "LastName", "email", "salary"]
  }'
```

Expected: `201` with 4 rows (Engineering only), 4 columns, names uppercased.

**Upload semicolon-delimited file:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/orders_semicolon.csv"
```

Expected: `201` with auto-detected semicolon delimiter, 4 rows.

**Error case — wrong file type:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/sample.json"
```

Expected: `400` with `"Invalid file type '.json'. Expected .csv, .tsv, or .txt"`.

### Step 6: Test File Upload — JSON to CSV

**Upload with no rules:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json"
```

Expected: `201` with 5 rows, 5 columns.

**Upload with all rules combined:**

```bash
curl -s -X POST http://localhost:8001/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json" \
  -F 'rules={
    "column_mapping": {"name": "Product Name", "brand": "Brand", "price": "Price (USD)"},
    "exclude_columns": ["id"],
    "transforms": {"Brand": "uppercase"},
    "default_values": {"in_stock": "unknown"},
    "column_order": ["Product Name", "Brand", "Price (USD)", "in_stock"],
    "delimiter": ";",
    "quote_data": false
  }'
```

Expected: `201` with 5 rows, 4 columns, semicolon-delimited output, brands uppercased.

### Step 7: Test Job Management

**List all jobs:**

```bash
curl -s http://localhost:8001/api/mapping/file/jobs/
```

**Filter by status:**

```bash
curl -s http://localhost:8001/api/mapping/file/jobs/?status=completed
curl -s http://localhost:8001/api/mapping/file/jobs/?status=failed
```

**Filter by direction:**

```bash
curl -s http://localhost:8001/api/mapping/file/jobs/?direction=csv_to_json
curl -s http://localhost:8001/api/mapping/file/jobs/?direction=json_to_csv
```

**Get job detail** (replace `<job_id>` with an actual UUID from the list response):

```bash
curl -s http://localhost:8001/api/mapping/file/jobs/<job_id>/
```

**Download output file:**

```bash
curl -o output_file.json http://localhost:8001/api/mapping/file/jobs/<job_id>/download/
```

### Step 8: Test the Web UI

Open http://localhost:8001/ in a browser.

#### CSV to JSON (File Upload with Dynamic Rules)

1. Ensure the **CSV → JSON** toggle is selected (active by default on the left)
2. Upload a CSV file — either **drag & drop** onto the upload zone, or **click** the zone to browse (accepts `.csv`, `.tsv`, `.txt`)
   - Try with `test_data/employees.csv` or `test_data/orders_semicolon.csv`
3. After upload, the **Transformation Rules** panel on the right auto-detects all columns and shows a per-column configuration card:
   - **Checkbox** — uncheck to exclude a column from the output
   - **Rename** — type a new name (leave blank to keep original)
   - **Transform** — select: UPPER, lower, Title, or Trim
   - **Default** — fill value for missing/empty data
   - **Filter =** — keep only rows where this column equals the entered value
4. Use the **Column Order** section to reorder output columns with the up/down arrow buttons
5. The **Rules Payload** section shows a live JSON preview of the rules that will be sent — updates in real-time as you configure. Click **Copy** to copy the payload.
6. Click **Convert File**
7. View the result below:
   - Green **Completed** badge with row count, column count, and output filename
   - **JSON output preview** — click **Copy** to copy to clipboard
   - Click **Show processing logs** to see step-by-step rule application details
   - Click **Download File** to save the `.json` output

**Example — Filter + Rename + Transform:**

1. Upload `test_data/employees.csv` (10 rows, 8 columns detected)
2. Uncheck the `id` checkbox to exclude it
3. Type `FirstName` in the **Rename** field for `first_name`
4. Select **UPPER** in the **Transform** dropdown for `first_name`
5. Type `Engineering` in the **Filter =** field for `department`
6. Check the **Rules Payload** preview — it should show:
   ```json
   {
     "filter_rules": { "department": "Engineering" },
     "column_mapping": { "first_name": "FirstName" },
     "include_columns": ["FirstName", "last_name", "email", "department", "salary", "hire_date", "is_active"],
     "transforms": { "FirstName": "uppercase" }
   }
   ```
7. Click **Convert File** — result: 4 rows (Engineering only), 7 columns, first names uppercased

#### JSON to CSV (File Upload with Dynamic Rules)

1. Click the **JSON → CSV** toggle on the right
2. Upload a `.json` file (e.g., `test_data/sample.json`) — columns are auto-detected from JSON keys
3. Configure rules in the sidebar — same per-column controls as above
4. **CSV Options** section appears at the bottom:
   - **Quote data fields** checkbox (default: checked)
   - **Quote header row** checkbox (default: unchecked)
   - **Delimiter** field (e.g., `;` for semicolon-separated output)
5. Check the **Rules Payload** preview, then click **Convert File**

#### Conversion History

1. Click the **History** tab in the header
2. Browse all past conversion jobs with status, row counts, and timestamps
3. Filter by **Status** (Completed, Failed, Processing) or **Type** (CSV to JSON, JSON to CSV)
4. Click **Download** on any completed job to re-download the output file
5. Click **Refresh** to reload the list

---

## Testing with Postman

### Step 1: Import the Collection

1. Open Postman
2. Click **Import** (top-left)
3. Select file: `test_data/CSV_JSON_Converter.postman_collection.json`
4. The collection **CSV/JSON Converter API** appears in your sidebar

### Step 2: Ensure the Server is Running

```bash
docker compose up -d
docker compose exec web python manage.py migrate
```

Verify at http://localhost:8001/api/mapping/registry/

### Step 3: Run the Requests

The collection has **7 folders** with **31 requests**:

| Folder | Requests | Description |
|--------|----------|-------------|
| **Registry** | 2 | List and search mappers |
| **Raw Content - CSV to JSON** | 5 | Raw string CSV conversions + error case |
| **Raw Content - JSON to CSV** | 7 | Raw string JSON conversions + error cases |
| **Raw Content - Generic Convert** | 3 | Generic mapper endpoint + error case |
| **File Upload - CSV to JSON** | 7 | File uploads with various rule combinations |
| **File Upload - JSON to CSV** | 4 | File uploads with rules for JSON->CSV |
| **Job Management** | 6 | List, filter, detail, and download jobs |

### Step 4: File Upload Requests

For file upload requests:

1. Open the request (e.g., **Upload CSV with ALL Rules Combined**)
2. Go to **Body** tab — it's already set to **form-data**
3. On the `file` row, click **Select Files** and pick a file from `test_data/`
4. The `rules` field already has the JSON pre-filled
5. Click **Send**

### Step 5: Download Output Files

1. Run **List All Jobs** to get a `job_id`
2. Open **Get Job Detail** and replace `PASTE-JOB-ID-HERE` in the URL with the actual ID
3. Open **Download Output File**, replace the ID, and click **Send and Download**

### Postman Collection Variable

The collection uses `{{base_url}}` = `http://localhost:8001`. To change it:

1. Click on the collection name
2. Go to **Variables** tab
3. Update `base_url`

---

## Test Data Files

| File | Format | Rows | Description |
|------|--------|------|-------------|
| `employees.csv` | Comma-delimited | 10 | Employee records (id, name, email, department, salary, hire_date, is_active) |
| `products.csv` | Comma-delimited | 5 | Product catalog (sku, name, category, price, stock, supplier) |
| `orders_semicolon.csv` | Semicolon-delimited | 4 | Orders (tests delimiter auto-detection) |
| `sample.json` | JSON array | 5 | Product objects (id, name, brand, price, in_stock) |

## Features

- **File upload with rules** — Upload CSV/JSON files, apply transformation rules, get converted files
- **Job tracking** — Every file conversion is tracked with status, logs, rules, and timestamps
- **Output file storage** — Input and output files saved to `media/conversions/<job_id>/`
- **Downloadable results** — Download converted files via the job download endpoint
- **Transformation rules engine** — Filter, rename, include/exclude, reorder, transform, and set defaults
- **Auto-detect CSV delimiter** — Comma, tab, semicolon, or pipe
- **Single object handling** — JSON to CSV accepts both `{}` and `[{}]`
- **Full key collection** — All unique keys across all JSON objects become CSV columns
- **Configurable quoting** — Control header and data quoting independently
- **Processing logs** — Every conversion returns detailed diagnostic logs
- **Registry pattern** — All mappers registered with stable IDs, validated at startup

## Adding a New Mapper

1. Create a file in `apps/mapping/maps/` (e.g., `xml_to_json.py`):

```python
def xml_to_json_mapper(content: str, **kwargs) -> dict:
    """Convert XML string to JSON."""
    logs = []
    # ... your conversion logic ...
    return {
        "output": output_string,
        "logs": logs,
        "output_type": "JSON",
    }
```

2. Register it in `apps/mapping/registry.py`:

```python
from .maps.xml_to_json import xml_to_json_mapper

MAPPING_REGISTRY = {
    # ... existing entries ...
    "xml_to_json": {
        "id": 5,
        "function": xml_to_json_mapper,
        "production": True,
    },
}
```

3. Immediately available via `GET /api/mapping/registry/` and `POST /api/mapping/convert/`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `True` | Django debug mode |
| `SECRET_KEY` | insecure dev key | Django secret key (change in production) |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hosts |

## Tech Stack

- Python 3.12
- Django 5.2
- Django REST Framework 3.16
- Docker
