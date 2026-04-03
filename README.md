# Data Integrator — JSON & CSV Converter

A Django REST Framework application that converts between **JSON and CSV** formats using **user-defined Python rule functions**. Users upload a file, write a `def apply_rules(row):` function to modify each row, and get the converted output with a live preview.

**Supported conversions:**
- **JSON to CSV** — Upload a JSON file (array of objects), get a CSV file
- **CSV to JSON** — Upload a CSV file, get a JSON file (array of objects)

## Quick Start

### Prerequisites

- Python 3.10+
- Docker and Docker Compose (optional)

### Run with Docker

```bash
docker compose up -d
docker compose exec web python manage.py migrate
```

The app will be available at **http://localhost:8001**.

### Run without Docker (Local Development)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py runserver
```

The app will be available at **http://127.0.0.1:8000**.

## How It Works

1. **Select direction** — JSON to CSV or CSV to JSON
2. **Upload** a file (JSON or CSV depending on direction)
3. **Preview** the first 5 rows in a data table
4. **Write a Python `apply_rules` function** in the code editor
5. **Convert** and preview the output
6. **Download** the output file

### Detailed Workflow (End to End)

Below is the complete request lifecycle — from opening the browser to downloading the output — with every endpoint, file, and function involved. The workflow is the same for both directions (JSON to CSV and CSV to JSON), with the direction-specific differences noted.

---

#### Step 1: Load the Web UI

```
Browser  ──GET /──▶  Django (converter/urls.py)
                      │
                      └─▶ TemplateView renders templates/index.html
                           │
                           └─▶ Single-page HTML returned to browser
```

**What happens:**
- `converter/urls.py:10` — routes `GET /` to `TemplateView(template_name="index.html")`
- `templates/index.html` — contains the full UI (HTML + CSS + JavaScript), no frameworks
- The browser renders two tabs: **Convert** (active) and **History**

---

#### Step 1b: Select Conversion Direction (Client-Side Only)

```
User clicks "JSON to CSV" or "CSV to JSON" button
  │
  └─▶ index.html → direction switching handler
       │
       ├─▶ Sets `currentDirection` to "json_to_csv" or "csv_to_json"
       ├─▶ Updates upload label, file extension filter, button text
       ├─▶ Shows/hides CSV-specific options (quote data, quote header)
       └─▶ Resets form state (clears file, preview, results)
```

**What happens:**
- The direction selector is a toggle at the top of the Convert page
- Switching direction changes the accepted file type (`.json` or `.csv`)
- CSV-to-JSON mode hides the "Quote data" and "Quote header" options (not applicable)
- The Convert button text updates to "Convert to CSV" or "Convert to JSON"

---

#### Step 2: Upload a File (Client-Side Only)

```
User drags file onto upload zone
  │
  └─▶ index.html → handleFile(file)
       │
       ├─▶ Stores file in JavaScript variable `selectedFile`
       ├─▶ Shows filename and size in the upload zone
       ├─▶ Reads first 64KB of the file: file.slice(0, 65536).text()
       ├─▶ If JSON direction: parseJSON(text, 5) — parses JSON, extracts up to 5 rows
       │   If CSV direction:  parseCSV(text, 5)  — parses CSV, extracts up to 5 rows
       ├─▶ showPreview(headers, rows) — renders the data preview table
       └─▶ Reveals Step 2 (preview) and Step 3 (code editor) cards
            Enables the Convert button
```

**What happens:**
- No API call is made — this is entirely client-side
- `handleFile()` — handles file selection from click or drag-drop
- `parseJSON()` — best-effort JSON parse for large files (reads only first 64KB)
- `parseCSV()` — parses CSV text by splitting lines and handling quoted fields
- `parseCSVLine()` — handles CSV quoting (double-quote escaping, delimiters inside quotes)
- `showPreview()` — builds an HTML table showing column headers and up to 5 rows
- The code editor is pre-filled with a template `def apply_rules(row):` function

---

#### Step 3: Write Transform Code (Client-Side Only)

```
User writes Python code in the code editor textarea
  │
  ├─▶ Optional: enters a function name (e.g., "clean_products")
  ├─▶ Optional: toggles CSV options (quote data, quote header, delimiter)
  └─▶ Clicks "Convert to CSV" or "Convert to JSON"
```

**What happens:**
- The code editor supports Tab key for 4-space indentation
- No validation happens client-side — the server validates the code

---

#### Step 4: Convert — POST to API

The frontend determines the endpoint based on `currentDirection`:

```
JSON to CSV:
Browser  ──POST /api/mapping/file/json-to-csv/──▶  apps/mapping/urls.py:9
           Fields: file, function_name, rules_code,  └─▶ FileUploadJsonToCsvView
                   delimiter, quote_data, quote_header

CSV to JSON:
Browser  ──POST /api/mapping/file/csv-to-json/──▶  apps/mapping/urls.py:10
           Fields: file, function_name, rules_code,  └─▶ FileUploadCsvToJsonView
                   delimiter
```

**Frontend sends the request:**
```javascript
const isJsonToCsv = currentDirection === 'json_to_csv';
const endpoint = isJsonToCsv ? 'json-to-csv' : 'csv-to-json';

const formData = new FormData();
formData.append('file', selectedFile);
formData.append('function_name', $functionName.value.trim());
formData.append('rules_code', $codeEditor.value);
formData.append('delimiter', ...);
if (isJsonToCsv) {
  formData.append('quote_data', ...);
  formData.append('quote_header', ...);
}

const resp = await fetch(`${API_BASE}/file/${endpoint}/`, { method: 'POST', body: formData });
```

---

#### Step 5: Backend Processing

**JSON to CSV:** `FileUploadJsonToCsvView.post()` in `apps/mapping/views_file.py:29`
**CSV to JSON:** `FileUploadCsvToJsonView.post()` in `apps/mapping/views_file.py:140`

Both views follow the same stages:

```
FileUploadJsonToCsvView.post(request)       FileUploadCsvToJsonView.post(request)
  │                                           │
  ├─▶ 5a. Validate request                   ├─▶ 5a. Validate request
  │     ├─▶ Check file exists                 │     ├─▶ Check file exists
  │     └─▶ Check extension is .json          │     └─▶ Check extension is .csv
  │
  ├─▶ 5b. Create ConversionJob record (status: "pending")
  │     └─▶ apps/mapping/models.py:14 — ConversionJob.objects.create(
  │           direction="json_to_csv",
  │           input_filename=filename,
  │           function_name=function_name,
  │           rules_code=rules_code,
  │         )
  │         Job gets a UUID primary key (e.g., a649949a-bf76-...)
  │
  ├─▶ 5c. Read file content + save input file
  │     ├─▶ content = uploaded_file.read().decode("utf-8")
  │     └─▶ job.input_file.save(filename, ...)
  │         Saved to: media/conversions/<job_id>/input/<filename>
  │
  ├─▶ 5d. Update job status to "processing"
  │
  ├─▶ 5e. Call the mapper
  │     ├─▶ JSON to CSV: json_to_csv_file_mapper(content, rules_code, delimiter, ...)
  │     └─▶ CSV to JSON: csv_to_json_file_mapper(content, rules_code, delimiter)
  │         (see Step 6 below)
  │
  ├─▶ 5f. Save output file
  │     ├─▶ job.output_file.save(output_filename, ContentFile(output_bytes))
  │     │   JSON to CSV: media/conversions/<job_id>/output/<filename>.csv
  │     │   CSV to JSON: media/conversions/<job_id>/output/<filename>.json
  │     ├─▶ job.status = "completed"
  │     ├─▶ job.rows_processed = result["rows_processed"]
  │     ├─▶ job.columns_count = result["columns_count"]
  │     ├─▶ job.logs = "\n".join(result["logs"])
  │     └─▶ job.save()
  │
  └─▶ 5g. Return JSON response (HTTP 201)
        {
          "job_id": "a649949a-...",
          "status": "completed",
          "direction": "json_to_csv" or "csv_to_json",
          "input_filename": "sample.json" or "products.csv",
          "output_filename": "sample.csv" or "products.json",
          "rows_processed": 4,
          "columns_count": 9,
          "function_name": "clean_products",
          "logs": ["Parsed 5 row(s)...", ...],
          "output": "<CSV string or JSON string>",
          "download_url": "http://localhost:8000/api/mapping/file/jobs/<job_id>/download/"
        }
```

**On error** (5e or any step fails):
```
  └─▶ job.status = "failed"
      job.error_message = str(e)
      Returns HTTP 400:
      {
        "job_id": "...",
        "error": "Conversion failed",
        "details": "name 'counter' is not defined"
      }
```

---

#### Step 6a: Mapper — JSON to CSV Conversion

`apps/mapping/maps/json_to_csv_file.py:15` — `json_to_csv_file_mapper()`

```
json_to_csv_file_mapper(content, rules_code, delimiter, quote_data, quote_header)
  │
  ├─▶ 6a. Parse JSON string
  │     ├─▶ json.loads(content) → list of dicts
  │     ├─▶ If single object → wrap in array
  │     └─▶ Validate: must be a non-empty list of dicts
  │
  ├─▶ 6b. Collect original column names
  │     └─▶ _collect_all_keys(data) — scans all rows, preserves insertion order
  │         Logs: "Parsed 5 row(s) with 5 column(s)"
  │         Logs: "Input columns: id, name, brand, price, in_stock"
  │
  ├─▶ 6c. Apply user rules (if rules_code is provided)
  │     └─▶ execute_rules(data, rules_code, logs)
  │         (see Step 7 below)
  │
  ├─▶ 6d. Collect final column names (may differ after apply_rules)
  │     └─▶ _collect_all_keys(data)
  │         Logs: "Output: 4 row(s) with 9 column(s)"
  │         Logs: "Output columns: row_num, sku, product_name, ..."
  │
  └─▶ 6e. Build CSV output
        ├─▶ Write header row (csv.writer, quoting depends on quote_header)
        ├─▶ Write data rows (csv.DictWriter, quoting depends on quote_data)
        │   Each value is cast to str, None becomes ""
        └─▶ Returns:
            {
              "output": "<full CSV string>",
              "logs": [...],
              "output_type": "CSV",
              "rows_processed": 4,
              "columns_count": 9
            }
```

---

#### Step 6b: Mapper — CSV to JSON Conversion

`apps/mapping/maps/csv_to_json_file.py:15` — `csv_to_json_file_mapper()`

```
csv_to_json_file_mapper(content, rules_code, delimiter)
  │
  ├─▶ 6a. Parse CSV string
  │     ├─▶ csv.DictReader(content, delimiter=delimiter) → list of dicts
  │     ├─▶ Extract fieldnames from header row
  │     └─▶ Validate: must have headers and at least one data row
  │         Note: All CSV values are strings (e.g., "1299.99", "true")
  │
  ├─▶ 6b. Collect original column names
  │     └─▶ _collect_all_keys(data)
  │         Logs: "Parsed 5 row(s) with 5 column(s)"
  │         Logs: "Input columns: id, name, brand, price, in_stock"
  │
  ├─▶ 6c. Apply user rules (if rules_code is provided)
  │     └─▶ execute_rules(data, rules_code, logs)
  │         (see Step 7 below)
  │
  ├─▶ 6d. Collect final column names (may differ after apply_rules)
  │     └─▶ _collect_all_keys(data)
  │         Logs: "Output: 5 row(s) with 5 column(s)"
  │
  └─▶ 6e. Build JSON output
        └─▶ json.dumps(data, indent=2, ensure_ascii=False)
            Returns:
            {
              "output": "[{\"id\": \"1\", \"name\": \"Laptop Pro\", ...}, ...]",
              "logs": [...],
              "output_type": "JSON",
              "rows_processed": 5,
              "columns_count": 5
            }
```

> **Important:** CSV values are always strings. In your `apply_rules` function, use `int()`, `float()`, or comparisons like `row['in_stock'] == 'true'` to convert types before they are written to JSON output.

---

#### Step 7: Executor — Sandboxed Code Execution

`apps/mapping/executor.py:82` — `execute_rules()`

```
execute_rules(data, code, logs)
  │
  ├─▶ 7a. Validate code — validate_code() (executor.py:66)
  │     ├─▶ Regex check against BLOCKED_PATTERNS:
  │     │     import, open(), eval(), exec(), compile(),
  │     │     globals(), locals(), getattr(), setattr(), delattr(),
  │     │     __dunder__, os, sys, subprocess
  │     └─▶ Check "def apply_rules(" exists in code
  │         Raises ValueError if any check fails
  │
  ├─▶ 7b. Execute code in sandbox
  │     ├─▶ safe_globals = {"__builtins__": SAFE_BUILTINS}
  │     │   SAFE_BUILTINS only includes: str, int, float, bool, len,
  │     │   list, dict, tuple, set, round, min, max, abs, sum, any,
  │     │   all, enumerate, zip, sorted, reversed, range, map,
  │     │   filter, isinstance, type, print, None, True, False
  │     └─▶ exec(code, safe_globals)
  │         This defines apply_rules() + any top-level variables
  │         (e.g., counter, brand_country) in safe_globals
  │
  ├─▶ 7c. Extract apply_rules function
  │     └─▶ transform_fn = safe_globals.get("apply_rules")
  │         Verify it's callable
  │
  └─▶ 7d. Apply rules to each row
        │
        for each row in data:
        │  ├─▶ Deep copy the row (original data is preserved)
        │  ├─▶ result = transform_fn(row_copy)
        │  ├─▶ If result is None → row is filtered out (skipped)
        │  ├─▶ If result is not a dict → TypeError
        │  ├─▶ If result is a dict → added to output
        │  └─▶ On exception → error logged, row skipped
        │       (stops after 10 errors)
        │
        └─▶ Returns: list of transformed row dicts
            Logs: "Transform complete: 5 input -> 4 output rows"
```

---

#### Step 8: Frontend Displays Result

```
Browser receives JSON response
  │
  ├─▶ On success → showSuccess(data)  (index.html line 593)
  │     ├─▶ Shows green "Completed" badge
  │     ├─▶ Shows stats: rows processed, columns count, output filename
  │     ├─▶ Shows CSV output in dark-themed preview box
  │     ├─▶ Shows "Download CSV" button (links to download endpoint)
  │     └─▶ Shows collapsible processing logs
  │
  └─▶ On error → showError(data)  (index.html line 607)
        ├─▶ Shows red "Failed" badge
        └─▶ Shows error message in the output preview box
```

---

#### Step 9: Download the CSV File

```
User clicks "Download CSV"
  │
  └─▶ GET /api/mapping/file/jobs/<job_id>/download/
       │
       ├─▶ converter/urls.py:9 → include("apps.mapping.urls")
       ├─▶ apps/mapping/urls.py:14 → ConversionJobDownloadView
       └─▶ apps/mapping/views_file.py:212
            │
            ├─▶ Fetch ConversionJob by UUID (404 if not found)
            ├─▶ Check job.status == "completed" (400 if not)
            ├─▶ Check job.output_file exists (404 if not)
            └─▶ Return FileResponse(job.output_file, as_attachment=True)
                 Browser downloads: sample.csv
```

---

#### Step 10: View Job History

```
User clicks "History" tab
  │
  └─▶ loadJobs()  (index.html line 635)
       │
       └─▶ GET /api/mapping/file/jobs/?status=<optional filter>
            │
            ├─▶ apps/mapping/urls.py:12 → ConversionJobListView
            └─▶ apps/mapping/views_file.py:140
                 │
                 ├─▶ ConversionJob.objects.all() (ordered by -created_at)
                 ├─▶ Optional filters: ?status=completed, ?direction=json_to_csv
                 ├─▶ Limit: 50 jobs max
                 └─▶ Returns JSON:
                      {
                        "count": 12,
                        "results": [
                          {
                            "job_id": "...",
                            "input_filename": "sample.json",
                            "output_filename": "sample.csv",
                            "status": "completed",
                            "rows_processed": 4,
                            "function_name": "clean_products",
                            "created_at": "2026-04-02T...",
                            "download_url": "http://..."
                          },
                          ...
                        ]
                      }

Browser renders:
  ├─▶ Table with columns: File, Function, Status, Rows, Date, Action
  ├─▶ Status badges (green/red/yellow)
  ├─▶ Download links for completed jobs
  └─▶ Filter dropdown + Refresh button
```

---

#### Viewing a Single Job Detail

```
GET /api/mapping/file/jobs/<job_id>/
  │
  ├─▶ apps/mapping/urls.py:13 → ConversionJobDetailView
  └─▶ apps/mapping/views_file.py:183
       │
       └─▶ Returns full job details including:
            rules_code, logs, error_message, timestamps, download_url
```

---

### File and Function Summary

| Step | File | Function / Class | Purpose |
|------|------|-----------------|---------|
| 1 | `converter/urls.py:10` | `TemplateView` | Serve the web UI |
| 1b | `templates/index.html` | direction switching handler | Switch between JSON-to-CSV and CSV-to-JSON |
| 2 | `templates/index.html` | `handleFile()` | Handle file upload (client-side) |
| 2 | `templates/index.html` | `parseJSON()` | Parse JSON for preview (client-side) |
| 2 | `templates/index.html` | `parseCSV()` | Parse CSV for preview (client-side) |
| 2 | `templates/index.html` | `parseCSVLine()` | Handle quoted CSV fields (client-side) |
| 2 | `templates/index.html` | `showPreview()` | Render data preview table (client-side) |
| 4 | `templates/index.html` | `$btnConvert click` | Send POST request with FormData |
| 5 | `apps/mapping/views_file.py` | `FileUploadJsonToCsvView` | Handle JSON upload, create job, call mapper |
| 5 | `apps/mapping/views_file.py` | `FileUploadCsvToJsonView` | Handle CSV upload, create job, call mapper |
| 5 | `apps/mapping/models.py` | `ConversionJob` | Database model for job tracking |
| 6a | `apps/mapping/maps/json_to_csv_file.py` | `json_to_csv_file_mapper()` | Parse JSON, apply rules, build CSV |
| 6b | `apps/mapping/maps/csv_to_json_file.py` | `csv_to_json_file_mapper()` | Parse CSV, apply rules, build JSON |
| 7 | `apps/mapping/executor.py` | `validate_code()` | Security validation of user code |
| 7 | `apps/mapping/executor.py` | `execute_rules()` | Sandbox execute apply_rules on each row |
| 8 | `templates/index.html` | `showSuccess()` | Display result with output preview |
| 8 | `templates/index.html` | `showError()` | Display error message |
| 9 | `apps/mapping/views_file.py` | `ConversionJobDownloadView` | Serve output file download |
| 10 | `apps/mapping/views_file.py` | `ConversionJobListView` | List all conversion jobs |
| 10 | `apps/mapping/views_file.py` | `ConversionJobDetailView` | Get single job details |
| 10 | `templates/index.html` | `loadJobs()` | Fetch and render job history (client-side) |

### Apply Rules Function

Users write a `def apply_rules(row):` function that receives each row as a Python dict and returns the modified dict. Return `None` to filter a row out.

```python
def apply_rules(row):
    # Rename columns
    row['Product Name'] = row.pop('name', '').upper()
    row['Brand Name'] = row.pop('brand', '')

    # Add new columns
    row['category'] = 'Electronics'
    row['discounted_price'] = round(float(row['price']) * 0.9, 2)

    # Remove a column
    del row['in_stock']

    # Filter out rows (return None to skip)
    if row.get('price') and float(row['price']) < 10:
        return None

    return row
```

**Available builtins:** `str`, `int`, `float`, `bool`, `len`, `list`, `dict`, `tuple`, `set`, `round`, `min`, `max`, `abs`, `sum`, `any`, `all`, `enumerate`, `zip`, `sorted`, `reversed`, `range`, `map`, `filter`, `isinstance`, `type`, `print`

**Blocked for security:** `import`, `open`, `eval`, `exec`, `compile`, `__dunder__` attributes, `os`, `sys`, `subprocess`

### Apply Rules Function Reference

All examples below use `test_data/sample.json`:

```json
[
  {"id": 1, "name": "Laptop Pro", "brand": "TechBrand", "price": 1299.99, "in_stock": true},
  {"id": 2, "name": "Wireless Earbuds", "brand": "SoundMax", "price": 79.99, "in_stock": true},
  {"id": 3, "name": "Smart Watch", "brand": "WristTech", "price": 249.99, "in_stock": false},
  {"id": 4, "name": "Tablet Mini", "brand": "TechBrand", "price": 449.99, "in_stock": true},
  {"id": 5, "name": "Bluetooth Speaker", "brand": "SoundMax", "price": 59.99, "in_stock": true}
]
```

---

#### Text Transforms

**Uppercase a text field:**
```python
def apply_rules(row):
    row['name'] = str(row['name']).upper()
    return row
# "Laptop Pro" → "LAPTOP PRO"
```

**Lowercase a text field:**
```python
def apply_rules(row):
    row['brand'] = str(row['brand']).lower()
    return row
# "TechBrand" → "techbrand"
```

**Title case:**
```python
def apply_rules(row):
    row['name'] = str(row['name']).title()
    return row
# "wireless earbuds" → "Wireless Earbuds"
```

**Strip whitespace:**
```python
def apply_rules(row):
    row['name'] = str(row['name']).strip()
    return row
```

**Replace text in a field:**
```python
def apply_rules(row):
    row['name'] = str(row['name']).replace('Pro', 'Professional')
    return row
# "Laptop Pro" → "Laptop Professional"
```

**Add a prefix or suffix:**
```python
def apply_rules(row):
    row['name'] = 'Product: ' + str(row['name'])
    row['brand'] = str(row['brand']) + ' Inc.'
    return row
# "Laptop Pro" → "Product: Laptop Pro", "TechBrand" → "TechBrand Inc."
```

**Truncate text to a max length:**
```python
def apply_rules(row):
    name = str(row['name'])
    row['name'] = name[:10] + '...' if len(name) > 10 else name
    return row
# "Wireless Earbuds" → "Wireless E..."
```

**Pad a field with leading zeros:**
```python
def apply_rules(row):
    row['id'] = str(row['id']).zfill(5)
    return row
# 1 → "00001", 5 → "00005"
```

**Extract part of a string (split):**
```python
def apply_rules(row):
    parts = str(row['name']).split(' ')
    row['first_word'] = parts[0]
    row['rest'] = ' '.join(parts[1:]) if len(parts) > 1 else ''
    return row
# "Laptop Pro" → first_word: "Laptop", rest: "Pro"
```

**Concatenate multiple fields:**
```python
def apply_rules(row):
    row['display'] = str(row['name']) + ' by ' + str(row['brand'])
    return row
# "Laptop Pro by TechBrand"
```

**Reverse a string:**
```python
def apply_rules(row):
    row['name'] = str(row['name'])[::-1]
    return row
# "Laptop Pro" → "orP potpaL"
```

**Check if text contains a substring:**
```python
def apply_rules(row):
    row['is_wireless'] = 'Wireless' in str(row['name']) or 'Bluetooth' in str(row['name'])
    return row
# Wireless Earbuds → True, Laptop Pro → False
```

**Convert boolean to readable text:**
```python
def apply_rules(row):
    row['availability'] = 'Available' if row.get('in_stock') else 'Out of Stock'
    return row
# true → "Available", false → "Out of Stock"
```

---

#### Add New Columns

**Add a column with a static value:**
```python
def apply_rules(row):
    row['category'] = 'Electronics'
    row['currency'] = 'USD'
    return row
```

**Add a computed column:**
```python
def apply_rules(row):
    row['discounted_price'] = round(float(row['price']) * 0.9, 2)
    return row
# price 1299.99 → discounted_price 1169.99
```

**Add tax and total:**
```python
def apply_rules(row):
    price = float(row['price'])
    row['tax'] = round(price * 0.08, 2)
    row['total'] = round(price * 1.08, 2)
    return row
# price 79.99 → tax 6.40, total 86.39
```

**Add a row number / sequence:**
```python
counter = {'n': 0}  # must be defined above apply_rules, in the same code block

def apply_rules(row):
    counter['n'] += 1
    row['row_num'] = counter['n']
    return row
# row_num: 1, 2, 3, 4, 5
```

> **Note:** Variables like `counter` must be defined **above** `def apply_rules(row):` in the same code submission. The sandbox executes the entire code block together — the `apply_rules` function can then reference those top-level variables.

**Add a price tier label:**
```python
def apply_rules(row):
    price = float(row['price'])
    if price >= 1000:
        row['tier'] = 'Premium'
    elif price >= 200:
        row['tier'] = 'Mid-Range'
    else:
        row['tier'] = 'Budget'
    return row
# 1299.99 → "Premium", 249.99 → "Mid-Range", 59.99 → "Budget"
```

**Add a field based on another field (lookup / mapping):**
```python
# Option A: lookup dict inside the function (re-created each row, but simple)
def apply_rules(row):
    brand_country = {
        'TechBrand': 'USA',
        'SoundMax': 'Japan',
        'WristTech': 'South Korea',
    }
    row['country'] = brand_country.get(row.get('brand'), 'Unknown')
    return row
# "TechBrand" → "USA", "SoundMax" → "Japan"
```

```python
# Option B: lookup dict above the function (created once, more efficient)
brand_country = {'TechBrand': 'USA', 'SoundMax': 'Japan', 'WristTech': 'South Korea'}

def apply_rules(row):
    row['country'] = brand_country.get(row.get('brand'), 'Unknown')
    return row
```

**Add a unique SKU from multiple fields:**
```python
def apply_rules(row):
    row['sku'] = str(row['brand'])[:3].upper() + '-' + str(row['id']).zfill(4)
    return row
# TechBrand id=1 → "TEC-0001", SoundMax id=2 → "SOU-0002"
```

---

#### Remove Columns

**Remove a single column:**
```python
def apply_rules(row):
    row.pop('in_stock', None)
    return row
```

**Remove multiple columns:**
```python
def apply_rules(row):
    for col in ['in_stock', 'brand']:
        row.pop(col, None)
    return row
```

**Keep only specific columns (remove everything else):**
```python
def apply_rules(row):
    return {k: row[k] for k in ['id', 'name', 'price'] if k in row}
# Output has only id, name, price columns
```

---

#### Rename Columns

**Rename a single column:**
```python
def apply_rules(row):
    row['product_name'] = row.pop('name', '')
    return row
# "name" column becomes "product_name"
```

**Rename multiple columns:**
```python
def apply_rules(row):
    renames = {
        'name': 'product_name',
        'brand': 'manufacturer',
        'price': 'unit_price',
        'in_stock': 'available',
    }
    for old, new in renames.items():
        if old in row:
            row[new] = row.pop(old)
    return row
```

**Rename columns to snake_case:**
```python
def apply_rules(row):
    return {k.lower().replace(' ', '_'): v for k, v in row.items()}
```

**Add a prefix to all column names:**
```python
def apply_rules(row):
    return {'product_' + k: v for k, v in row.items()}
# id → product_id, name → product_name, etc.
```

---

#### Filter Rows

**Filter by exact value:**
```python
def apply_rules(row):
    if row.get('brand') != 'TechBrand':
        return None
    return row
# Keeps only TechBrand products (id 1, 4)
```

**Filter by numeric comparison:**
```python
def apply_rules(row):
    if float(row.get('price', 0)) < 100:
        return None
    return row
# Removes Wireless Earbuds (79.99) and Bluetooth Speaker (59.99)
```

**Filter by boolean field:**
```python
def apply_rules(row):
    if not row.get('in_stock'):
        return None
    return row
# Removes Smart Watch (in_stock: false)
```

**Filter by text contains:**
```python
def apply_rules(row):
    if 'Smart' not in str(row.get('name', '')):
        return None
    return row
# Keeps only "Smart Watch"
```

**Filter by text starts with / ends with:**
```python
def apply_rules(row):
    if not str(row.get('name', '')).startswith('Bluetooth'):
        return None
    return row
# Keeps only "Bluetooth Speaker"
```

**Filter by multiple conditions (AND):**
```python
def apply_rules(row):
    if row.get('brand') == 'TechBrand' and float(row.get('price', 0)) > 500:
        return row
    return None
# Keeps only Laptop Pro (TechBrand, 1299.99)
```

**Filter by multiple conditions (OR):**
```python
def apply_rules(row):
    if row.get('brand') == 'SoundMax' or float(row.get('price', 0)) > 1000:
        return row
    return None
# Keeps SoundMax products + Laptop Pro
```

**Filter by value in a list:**
```python
def apply_rules(row):
    allowed = ['TechBrand', 'WristTech']
    if row.get('brand') not in allowed:
        return None
    return row
# Keeps TechBrand and WristTech products
```

**Filter by price range:**
```python
def apply_rules(row):
    price = float(row.get('price', 0))
    if 50 <= price <= 300:
        return row
    return None
# Keeps Wireless Earbuds, Smart Watch, Bluetooth Speaker
```

---

#### Numeric Transforms

**Round a number:**
```python
def apply_rules(row):
    row['price'] = round(float(row['price']))
    return row
# 1299.99 → 1300, 79.99 → 80
```

**Format price as string with currency:**
```python
def apply_rules(row):
    row['price_display'] = '$' + str(round(float(row['price']), 2))
    return row
# 1299.99 → "$1299.99"
```

**Calculate percentage of a total:**
```python
total = 1299.99 + 79.99 + 249.99 + 449.99 + 59.99
def apply_rules(row):
    row['price_pct'] = str(round(float(row['price']) / total * 100, 1)) + '%'
    return row
# Laptop Pro → "60.7%"
```

**Clamp a value to a range:**
```python
def apply_rules(row):
    row['price'] = max(100, min(1000, float(row['price'])))
    return row
# 59.99 → 100, 1299.99 → 1000, 249.99 → 249.99
```

---

#### Reorder Columns

**Set a specific column order:**
```python
def apply_rules(row):
    order = ['id', 'brand', 'name', 'price', 'in_stock']
    return {k: row[k] for k in order if k in row}
```

**Move a column to the front:**
```python
def apply_rules(row):
    result = {'name': row.get('name')}
    result.update({k: v for k, v in row.items() if k != 'name'})
    return result
```

---

#### Conditional Transforms

**Set a value based on a condition:**
```python
def apply_rules(row):
    row['status'] = 'premium' if float(row['price']) > 500 else 'standard'
    return row
# 1299.99 → "premium", 79.99 → "standard"
```

**Apply different rules per brand:**
```python
def apply_rules(row):
    if row.get('brand') == 'TechBrand':
        row['price'] = round(float(row['price']) * 0.85, 2)   # 15% off
    elif row.get('brand') == 'SoundMax':
        row['price'] = round(float(row['price']) * 0.90, 2)   # 10% off
    return row
```

**Null / missing value handling:**
```python
def apply_rules(row):
    row['name'] = row.get('name') or 'Unnamed'
    row['price'] = float(row.get('price') or 0)
    return row
```

---

#### Type Conversions

**Convert all values to strings:**
```python
def apply_rules(row):
    return {k: str(v) for k, v in row.items()}
# true → "True", 1299.99 → "1299.99"
```

**Convert boolean to 1/0:**
```python
def apply_rules(row):
    row['in_stock'] = 1 if row.get('in_stock') else 0
    return row
# true → 1, false → 0
```

**Convert boolean to Yes/No:**
```python
def apply_rules(row):
    row['in_stock'] = 'Yes' if row.get('in_stock') else 'No'
    return row
```

---

#### Combining Multiple Operations

**Full apply_rules example with sample.json** (paste this entire block into the code editor):
```python
# These top-level variables are shared across all rows
counter = {'n': 0}
brand_country = {'TechBrand': 'USA', 'SoundMax': 'Japan', 'WristTech': 'South Korea'}

def apply_rules(row):
    # Filter: skip out-of-stock items
    if not row.get('in_stock'):
        return None

    counter['n'] += 1

    # Rename columns
    row['product_name'] = row.pop('name', '')
    row['manufacturer'] = row.pop('brand', '')

    # Text rules
    row['product_name'] = str(row['product_name']).upper()

    # Add new columns
    price = float(row['price'])
    row['tax'] = round(price * 0.08, 2)
    row['total'] = round(price * 1.08, 2)
    row['tier'] = 'Premium' if price >= 500 else 'Standard'
    row['country'] = brand_country.get(row['manufacturer'], 'Unknown')
    row['sku'] = str(row['manufacturer'])[:3].upper() + '-' + str(row['id']).zfill(4)
    row['row_num'] = counter['n']

    # Remove columns
    row.pop('in_stock', None)

    # Reorder
    order = ['row_num', 'sku', 'product_name', 'manufacturer', 'country',
             'price', 'tax', 'total', 'tier']
    return {k: row.get(k) for k in order}
```

**Output:**
| row_num | sku | product_name | manufacturer | country | price | tax | total | tier |
|---|---|---|---|---|---|---|---|---|
| 1 | TEC-0001 | LAPTOP PRO | TechBrand | USA | 1299.99 | 104.0 | 1403.99 | Premium |
| 2 | SOU-0002 | WIRELESS EARBUDS | SoundMax | Japan | 79.99 | 6.4 | 86.39 | Standard |
| 3 | TEC-0004 | TABLET MINI | TechBrand | USA | 449.99 | 36.0 | 485.99 | Standard |
| 4 | SOU-0005 | BLUETOOTH SPEAKER | SoundMax | Japan | 59.99 | 4.8 | 64.79 | Standard |

### CSV to JSON Apply Rules Examples

When converting CSV to JSON, all values start as **strings** (CSV has no type information). Use the `apply_rules` function to cast types and restructure data.

All examples below use `test_data/products.csv`:

```csv
sku,product_name,category,price,stock_qty,supplier
SKU-001,Wireless Mouse,Electronics,29.99,150,TechCorp
SKU-002,USB-C Hub,Electronics,49.99,85,TechCorp
SKU-003,Standing Desk,Furniture,399.00,12,OfficePro
SKU-004,Mechanical Keyboard,Electronics,89.99,200,KeyMaster
SKU-005,Monitor Arm,Furniture,129.99,45,OfficePro
```

> **Important:** All CSV values are strings. `row['price']` is `"29.99"` (string), not `29.99` (float). Cast types explicitly in your `apply_rules` function.

---

#### Quick Reference Table — All Transform Rules for products.csv

| # | Rule | Function | Code |
|---|------|----------|------|
| | **Text Transforms** | | |
| 1 | Uppercase | `row['product_name'].upper()` | `row['product_name'] = row['product_name'].upper()` |
| 2 | Lowercase | `row['supplier'].lower()` | `row['supplier'] = row['supplier'].lower()` |
| 3 | Title case | `row['product_name'].title()` | `row['product_name'] = row['product_name'].title()` |
| 4 | Strip whitespace | `row['product_name'].strip()` | `row['product_name'] = row['product_name'].strip()` |
| 5 | Replace text | `row['product_name'].replace('USB-C', 'Type-C')` | `row['product_name'] = row['product_name'].replace('USB-C', 'Type-C')` |
| 6 | Add prefix | `'Product: ' + row['product_name']` | `row['product_name'] = 'Product: ' + row['product_name']` |
| 7 | Add suffix | `row['supplier'] + ' Ltd.'` | `row['supplier'] = row['supplier'] + ' Ltd.'` |
| 8 | Truncate | `row['product_name'][:12] + '...'` | `name = row['product_name']; row['product_name'] = name[:12] + '...' if len(name) > 12 else name` |
| 9 | Pad zeros | `num.zfill(6)` | `num = row['sku'].split('-')[1]; row['sku'] = 'SKU-' + num.zfill(6)` |
| 10 | Split string | `row['product_name'].split(' ')` | `parts = row['product_name'].split(' '); row['first_word'] = parts[0]` |
| 11 | Concatenate | `row['product_name'] + ' (' + row['sku'] + ')'` | `row['display'] = row['product_name'] + ' (' + row['sku'] + ')'` |
| 12 | Reverse | `row['product_name'][::-1]` | `row['product_name'] = row['product_name'][::-1]` |
| 13 | Contains check | `'USB' in row['product_name']` | `row['is_usb'] = 'USB' in row['product_name']` |
| 14 | Starts with | `row['product_name'].startswith('Wireless')` | Use in filter: `if not row['product_name'].startswith('Wireless'): return None` |
| 15 | Ends with | `row['product_name'].endswith('Desk')` | Use in filter: `if not row['product_name'].endswith('Desk'): return None` |
| 16 | Availability text | `int(row['stock_qty'])` condition | `row['availability'] = 'Low Stock' if int(row['stock_qty']) < 20 else 'In Stock'` |
| | **Add New Columns** | | |
| 17 | Static value | `row['key'] = 'value'` | `row['currency'] = 'USD'` |
| 18 | Computed (discount) | `round(price * 0.9, 2)` | `row['discount_10pct'] = round(float(row['price']) * 0.9, 2)` |
| 19 | Tax & total | `round(price * 1.08, 2)` | `p = float(row['price']); row['tax'] = round(p * 0.08, 2); row['total'] = round(p * 1.08, 2)` |
| 20 | Row number | `counter['n'] += 1` | Define `counter = {'n': 0}` above apply_rules; `counter['n'] += 1; row['row_num'] = counter['n']` |
| 21 | Price tier | `if price >= 200: 'Premium'` | `p = float(row['price']); row['tier'] = 'Premium' if p >= 200 else 'Mid-Range' if p >= 50 else 'Budget'` |
| 22 | Lookup / mapping | `dict.get(row['supplier'])` | `row['country'] = {'TechCorp':'USA','OfficePro':'Germany','KeyMaster':'Japan'}.get(row['supplier'],'Unknown')` |
| 23 | Inventory value | `price * qty` | `row['inventory_value'] = round(float(row['price']) * int(row['stock_qty']), 2)` |
| 24 | Product code | `category[:3] + sku_num` | `row['product_code'] = row['category'][:3].upper() + '-' + row['sku'].split('-')[1]` |
| | **Remove Columns** | | |
| 25 | Remove single | `row.pop('col', None)` | `row.pop('stock_qty', None)` |
| 26 | Remove multiple | `for col in [...]: row.pop(col, None)` | `for col in ['stock_qty', 'supplier']: row.pop(col, None)` |
| 27 | Keep only listed | `{k: row[k] for k in [...]}`  | `return {k: row[k] for k in ['sku', 'product_name', 'price'] if k in row}` |
| 28 | Remove by pattern | `if 'qty' not in k` | `return {k: v for k, v in row.items() if 'qty' not in k.lower()}` |
| | **Rename Columns** | | |
| 29 | Rename single | `row.pop('old')` | `row['name'] = row.pop('product_name', '')` |
| 30 | Rename multiple | `for old, new in renames.items()` | `renames = {'product_name':'name','price':'unit_price'}; [row update loop]` |
| 31 | To camelCase | `parts[0] + parts[1:].title()` | `return {to_camel(k): v for k, v in row.items()}` |
| 32 | Prefix all | `'prefix_' + k` | `return {'product_' + k: v for k, v in row.items()}` |
| 33 | Uppercase all | `k.upper()` | `return {k.upper(): v for k, v in row.items()}` |
| | **Filter Rows** | | |
| 34 | Exact match | `row['category'] != 'Electronics'` | `if row['category'] != 'Electronics': return None` |
| 35 | Numeric comparison | `float(row['price']) < 50` | `if float(row['price']) < 50: return None` |
| 36 | Stock level | `int(row['stock_qty']) < 50` | `if int(row['stock_qty']) < 50: return None` |
| 37 | Text contains | `'Mouse' not in row['product_name']` | `if 'Mouse' not in row['product_name']: return None` |
| 38 | AND condition | `category == 'X' and price > N` | `if row['category'] == 'Electronics' and float(row['price']) > 50: return row` |
| 39 | OR condition | `supplier == 'X' or price >= N` | `if row['supplier'] == 'TechCorp' or float(row['price']) >= 100: return row` |
| 40 | Value in list | `row['supplier'] not in [...]` | `if row['supplier'] not in ['TechCorp', 'KeyMaster']: return None` |
| 41 | Price range | `30 <= price <= 100` | `p = float(row['price']); if not (30 <= p <= 100): return None` |
| 42 | SKU pattern | `int(row['sku'].split('-')[1])` | `if int(row['sku'].split('-')[1]) > 3: return None` |
| | **Numeric Transforms** | | |
| 43 | Cast to float | `float(row['price'])` | `row['price'] = float(row['price'])` |
| 44 | Cast to int | `int(row['stock_qty'])` | `row['stock_qty'] = int(row['stock_qty'])` |
| 45 | Safe cast | `try/except` | `try: row['price'] = float(row['price'])\nexcept ValueError: row['price'] = 0.0` |
| 46 | Round | `round(float(row['price']))` | `row['price'] = round(float(row['price']))` |
| 47 | Currency format | `'$' + str(price)` | `row['price_display'] = '$' + str(round(float(row['price']), 2))` |
| 48 | Clamp to range | `max(50, min(200, price))` | `row['price'] = max(50, min(200, float(row['price'])))` |
| | **Reorder Columns** | | |
| 49 | Specific order | `{k: row[k] for k in order}` | `return {k: row[k] for k in ['sku','product_name','category','supplier','price','stock_qty'] if k in row}` |
| 50 | Move to front | `result = {'col': row['col']}` | `result = {'product_name': row['product_name']}; result.update(...)` |
| | **Conditional Transforms** | | |
| 51 | If/else value | `'premium' if price > 100` | `row['status'] = 'premium' if float(row['price']) > 100 else 'standard'` |
| 52 | Per-supplier logic | `if row['supplier'] == 'X'` | `if row['supplier'] == 'TechCorp': row['price'] = round(float(row['price']) * 0.85, 2)` |
| 53 | Null handling | `row.get('col') or default` | `row['product_name'] = row.get('product_name') or 'Unnamed'` |
| | **Type Conversions** | | |
| 54 | String to number | `float()`, `int()` | `row['price'] = float(row['price']); row['stock_qty'] = int(row['stock_qty'])` |
| 55 | Stock to boolean | `int(row['stock_qty']) > 0` | `row['in_stock'] = int(row['stock_qty']) > 0` |
| 56 | Category to flags | `row['category'] == 'X'` | `row['is_electronics'] = row['category'] == 'Electronics'` |
| | **Nested JSON** | | |
| 57 | Group into objects | `return {'product': {...}, 'pricing': {...}}` | See "Restructure Flat CSV" example below |
| 58 | API-friendly format | `return {'productId': ..., 'productName': ...}` | See "API-friendly response" example below |

---

#### Text Transforms

**Uppercase a text field:**
```python
def apply_rules(row):
    row['product_name'] = row['product_name'].upper()
    return row
# "Wireless Mouse" → "WIRELESS MOUSE"
```

**Lowercase a text field:**
```python
def apply_rules(row):
    row['supplier'] = row['supplier'].lower()
    return row
# "TechCorp" → "techcorp"
```

**Title case:**
```python
def apply_rules(row):
    row['product_name'] = row['product_name'].title()
    return row
# "wireless mouse" → "Wireless Mouse"
```

**Strip whitespace:**
```python
def apply_rules(row):
    row['product_name'] = row['product_name'].strip()
    row['supplier'] = row['supplier'].strip()
    return row
```

**Replace text in a field:**
```python
def apply_rules(row):
    row['product_name'] = row['product_name'].replace('USB-C', 'Type-C')
    return row
# "USB-C Hub" → "Type-C Hub"
```

**Add a prefix or suffix:**
```python
def apply_rules(row):
    row['product_name'] = 'Product: ' + row['product_name']
    row['supplier'] = row['supplier'] + ' Ltd.'
    return row
# "Wireless Mouse" → "Product: Wireless Mouse", "TechCorp" → "TechCorp Ltd."
```

**Truncate text to a max length:**
```python
def apply_rules(row):
    name = row['product_name']
    row['product_name'] = name[:12] + '...' if len(name) > 12 else name
    return row
# "Mechanical Keyboard" → "Mechanical K..."
```

**Pad SKU with leading zeros:**
```python
def apply_rules(row):
    # Extract numeric part and re-pad
    num = row['sku'].split('-')[1]
    row['sku'] = 'SKU-' + num.zfill(6)
    return row
# "SKU-001" → "SKU-000001"
```

**Extract part of a string (split):**
```python
def apply_rules(row):
    parts = row['product_name'].split(' ')
    row['first_word'] = parts[0]
    row['rest'] = ' '.join(parts[1:]) if len(parts) > 1 else ''
    return row
# "Wireless Mouse" → first_word: "Wireless", rest: "Mouse"
```

**Concatenate multiple fields:**
```python
def apply_rules(row):
    row['display'] = row['product_name'] + ' (' + row['sku'] + ')'
    return row
# "Wireless Mouse (SKU-001)"
```

**Reverse a string:**
```python
def apply_rules(row):
    row['product_name'] = row['product_name'][::-1]
    return row
# "Wireless Mouse" → "esuoM sseleriW"
```

**Check if text contains a substring:**
```python
def apply_rules(row):
    row['is_usb'] = 'USB' in row['product_name']
    return row
# "USB-C Hub" → True, "Wireless Mouse" → False
```

**Convert stock quantity to availability text:**
```python
def apply_rules(row):
    qty = int(row['stock_qty'])
    if qty == 0:
        row['availability'] = 'Out of Stock'
    elif qty < 20:
        row['availability'] = 'Low Stock'
    elif qty < 100:
        row['availability'] = 'In Stock'
    else:
        row['availability'] = 'Plenty Available'
    return row
# 150 → "Plenty Available", 12 → "Low Stock"
```

---

#### Add New Columns

**Add a column with a static value:**
```python
def apply_rules(row):
    row['currency'] = 'USD'
    row['warehouse'] = 'Main'
    return row
```

**Add a computed column (discount price):**
```python
def apply_rules(row):
    price = float(row['price'])
    row['price'] = price
    row['discount_10pct'] = round(price * 0.9, 2)
    return row
# 29.99 → discount_10pct: 26.99
```

**Add tax and total:**
```python
def apply_rules(row):
    price = float(row['price'])
    row['price'] = price
    row['tax'] = round(price * 0.08, 2)
    row['total'] = round(price * 1.08, 2)
    return row
# 29.99 → tax: 2.40, total: 32.39
```

**Add a row number / sequence:**
```python
counter = {'n': 0}  # must be defined above apply_rules, in the same code block

def apply_rules(row):
    counter['n'] += 1
    row['row_num'] = counter['n']
    return row
# row_num: 1, 2, 3, 4, 5
```

> **Note:** Variables like `counter` must be defined **above** `def apply_rules(row):` in the same code submission. The sandbox executes the entire code block together.

**Add a price tier label:**
```python
def apply_rules(row):
    price = float(row['price'])
    if price >= 200:
        row['tier'] = 'Premium'
    elif price >= 50:
        row['tier'] = 'Mid-Range'
    else:
        row['tier'] = 'Budget'
    return row
# 399.00 → "Premium", 89.99 → "Mid-Range", 29.99 → "Budget"
```

**Add a field based on another field (lookup / mapping):**
```python
# Option A: lookup dict inside the function (re-created each row, but simple)
def apply_rules(row):
    supplier_country = {
        'TechCorp': 'USA',
        'OfficePro': 'Germany',
        'KeyMaster': 'Japan',
    }
    row['country'] = supplier_country.get(row['supplier'], 'Unknown')
    return row
# "TechCorp" → "USA", "OfficePro" → "Germany"
```

```python
# Option B: lookup dict above the function (created once, more efficient)
supplier_country = {'TechCorp': 'USA', 'OfficePro': 'Germany', 'KeyMaster': 'Japan'}

def apply_rules(row):
    row['country'] = supplier_country.get(row['supplier'], 'Unknown')
    return row
```

**Add inventory value (price x quantity):**
```python
def apply_rules(row):
    price = float(row['price'])
    qty = int(row['stock_qty'])
    row['price'] = price
    row['stock_qty'] = qty
    row['inventory_value'] = round(price * qty, 2)
    return row
# Wireless Mouse: 29.99 * 150 = 4498.50
```

**Generate a unique product code from multiple fields:**
```python
def apply_rules(row):
    row['product_code'] = row['category'][:3].upper() + '-' + row['sku'].split('-')[1]
    return row
# Electronics, SKU-001 → "ELE-001", Furniture, SKU-003 → "FUR-003"
```

---

#### Remove Columns

**Remove a single column:**
```python
def apply_rules(row):
    row.pop('stock_qty', None)
    return row
```

**Remove multiple columns:**
```python
def apply_rules(row):
    for col in ['stock_qty', 'supplier']:
        row.pop(col, None)
    return row
```

**Keep only specific columns (remove everything else):**
```python
def apply_rules(row):
    return {k: row[k] for k in ['sku', 'product_name', 'price'] if k in row}
# Output has only sku, product_name, price columns
```

**Remove columns by pattern (e.g., all columns containing "qty"):**
```python
def apply_rules(row):
    return {k: v for k, v in row.items() if 'qty' not in k.lower()}
# Removes stock_qty
```

---

#### Rename Columns

**Rename a single column:**
```python
def apply_rules(row):
    row['name'] = row.pop('product_name', '')
    return row
# "product_name" column becomes "name"
```

**Rename multiple columns:**
```python
def apply_rules(row):
    renames = {
        'product_name': 'name',
        'price': 'unit_price',
        'stock_qty': 'quantity',
        'supplier': 'vendor',
    }
    for old, new in renames.items():
        if old in row:
            row[new] = row.pop(old)
    return row
```

**Rename columns to camelCase:**
```python
def apply_rules(row):
    def to_camel(name):
        parts = name.split('_')
        return parts[0] + ''.join(p.title() for p in parts[1:])
    return {to_camel(k): v for k, v in row.items()}
# product_name → productName, stock_qty → stockQty
```

**Add a prefix to all column names:**
```python
def apply_rules(row):
    return {'product_' + k: v for k, v in row.items()}
# sku → product_sku, price → product_price, etc.
```

**Uppercase all column names:**
```python
def apply_rules(row):
    return {k.upper(): v for k, v in row.items()}
# sku → SKU, product_name → PRODUCT_NAME
```

---

#### Filter Rows

**Filter by exact value:**
```python
def apply_rules(row):
    if row['category'] != 'Electronics':
        return None
    return row
# Keeps: Wireless Mouse, USB-C Hub, Mechanical Keyboard
```

**Filter by numeric comparison:**
```python
def apply_rules(row):
    if float(row['price']) < 50:
        return None
    return row
# Removes: Wireless Mouse (29.99), USB-C Hub (49.99)
```

**Filter by stock level:**
```python
def apply_rules(row):
    if int(row['stock_qty']) < 50:
        return None
    return row
# Removes: Standing Desk (12), Monitor Arm (45)
```

**Filter by text contains:**
```python
def apply_rules(row):
    if 'Mouse' not in row['product_name'] and 'Keyboard' not in row['product_name']:
        return None
    return row
# Keeps: Wireless Mouse, Mechanical Keyboard
```

**Filter by text starts with / ends with:**
```python
def apply_rules(row):
    if not row['product_name'].startswith('Wireless'):
        return None
    return row
# Keeps only "Wireless Mouse"
```

```python
def apply_rules(row):
    if not row['product_name'].endswith('Desk'):
        return None
    return row
# Keeps only "Standing Desk"
```

**Filter by multiple conditions (AND):**
```python
def apply_rules(row):
    if row['category'] == 'Electronics' and float(row['price']) > 50:
        return row
    return None
# Keeps: Mechanical Keyboard (Electronics, 89.99)
```

**Filter by multiple conditions (OR):**
```python
def apply_rules(row):
    if row['supplier'] == 'TechCorp' or float(row['price']) >= 100:
        return row
    return None
# Keeps: Wireless Mouse, USB-C Hub (TechCorp), Standing Desk, Monitor Arm (>= 100)
```

**Filter by value in a list:**
```python
def apply_rules(row):
    allowed_suppliers = ['TechCorp', 'KeyMaster']
    if row['supplier'] not in allowed_suppliers:
        return None
    return row
# Keeps: TechCorp and KeyMaster products
```

**Filter by price range:**
```python
def apply_rules(row):
    price = float(row['price'])
    if 30 <= price <= 100:
        return row
    return None
# Keeps: USB-C Hub (49.99), Mechanical Keyboard (89.99)
```

**Filter by SKU pattern:**
```python
def apply_rules(row):
    sku_num = int(row['sku'].split('-')[1])
    if sku_num > 3:
        return None
    return row
# Keeps: SKU-001, SKU-002, SKU-003
```

---

#### Numeric Transforms

**Cast string values to proper types:**
```python
def apply_rules(row):
    row['price'] = float(row['price'])
    row['stock_qty'] = int(row['stock_qty'])
    return row
# "29.99" → 29.99, "150" → 150
```

**Safe type casting with defaults:**
```python
def apply_rules(row):
    try:
        row['price'] = float(row.get('price', '0'))
    except ValueError:
        row['price'] = 0.0
    try:
        row['stock_qty'] = int(row.get('stock_qty', '0'))
    except ValueError:
        row['stock_qty'] = 0
    return row
```

**Round a number:**
```python
def apply_rules(row):
    row['price'] = round(float(row['price']))
    return row
# 29.99 → 30, 399.00 → 399
```

**Format price as string with currency:**
```python
def apply_rules(row):
    row['price_display'] = '$' + str(round(float(row['price']), 2))
    return row
# 29.99 → "$29.99"
```

**Calculate percentage of total inventory value:**
```python
# Pre-calculate total (or hardcode for known data)
prices = [29.99, 49.99, 399.00, 89.99, 129.99]
qtys = [150, 85, 12, 200, 45]
total_value = sum(p * q for p, q in zip(prices, qtys))

def apply_rules(row):
    val = float(row['price']) * int(row['stock_qty'])
    row['inventory_value'] = round(val, 2)
    row['pct_of_total'] = str(round(val / total_value * 100, 1)) + '%'
    return row
```

**Clamp price to a range:**
```python
def apply_rules(row):
    row['price'] = max(50, min(200, float(row['price'])))
    return row
# 29.99 → 50, 399.00 → 200, 89.99 → 89.99
```

---

#### Reorder Columns

**Set a specific column order:**
```python
def apply_rules(row):
    order = ['sku', 'product_name', 'category', 'supplier', 'price', 'stock_qty']
    return {k: row[k] for k in order if k in row}
```

**Move a column to the front:**
```python
def apply_rules(row):
    result = {'product_name': row['product_name']}
    result.update({k: v for k, v in row.items() if k != 'product_name'})
    return result
```

---

#### Conditional Transforms

**Set a value based on a condition:**
```python
def apply_rules(row):
    row['status'] = 'premium' if float(row['price']) > 100 else 'standard'
    return row
# 399.00 → "premium", 29.99 → "standard"
```

**Apply different discounts per supplier:**
```python
def apply_rules(row):
    price = float(row['price'])
    if row['supplier'] == 'TechCorp':
        row['price'] = round(price * 0.85, 2)    # 15% off
    elif row['supplier'] == 'OfficePro':
        row['price'] = round(price * 0.90, 2)    # 10% off
    else:
        row['price'] = price
    return row
```

**Null / missing value handling:**
```python
def apply_rules(row):
    row['product_name'] = row.get('product_name') or 'Unnamed'
    row['price'] = float(row.get('price') or '0')
    row['stock_qty'] = int(row.get('stock_qty') or '0')
    return row
```

---

#### Type Conversions

**Convert all numeric strings to proper types:**
```python
def apply_rules(row):
    row['price'] = float(row['price'])
    row['stock_qty'] = int(row['stock_qty'])
    return row
# "29.99" → 29.99, "150" → 150
```

**Convert stock quantity to boolean availability:**
```python
def apply_rules(row):
    row['in_stock'] = int(row['stock_qty']) > 0
    return row
# 150 → True, 0 → False
```

**Convert category to boolean flags:**
```python
def apply_rules(row):
    row['is_electronics'] = row['category'] == 'Electronics'
    row['is_furniture'] = row['category'] == 'Furniture'
    return row
# Electronics → is_electronics: True, is_furniture: False
```

---

#### Restructure Flat CSV into Nested JSON

**Group fields into nested objects:**
```python
def apply_rules(row):
    return {
        'sku': row['sku'],
        'product': {
            'name': row['product_name'],
            'category': row['category'],
        },
        'pricing': {
            'amount': float(row['price']),
            'currency': 'USD',
        },
        'inventory': {
            'quantity': int(row['stock_qty']),
            'supplier': row['supplier'],
        },
    }
```

**Output:**
```json
{
  "sku": "SKU-001",
  "product": {"name": "Wireless Mouse", "category": "Electronics"},
  "pricing": {"amount": 29.99, "currency": "USD"},
  "inventory": {"quantity": 150, "supplier": "TechCorp"}
}
```

**Build an API-friendly response format:**
```python
def apply_rules(row):
    return {
        'productId': row['sku'],
        'productName': row['product_name'],
        'category': row['category'].lower(),
        'unitPrice': float(row['price']),
        'stockQuantity': int(row['stock_qty']),
        'vendor': row['supplier'],
        'isAvailable': int(row['stock_qty']) > 0,
    }
```

---

#### Combining Multiple Operations

**Full apply_rules example with products.csv** (paste this entire block into the code editor):
```python
# These top-level variables are shared across all rows
counter = {'n': 0}
supplier_info = {
    'TechCorp': {'country': 'USA', 'discount': 0.15},
    'OfficePro': {'country': 'Germany', 'discount': 0.10},
    'KeyMaster': {'country': 'Japan', 'discount': 0.05},
}

def apply_rules(row):
    # Filter: skip low-stock items (fewer than 20 units)
    qty = int(row['stock_qty'])
    if qty < 20:
        return None

    counter['n'] += 1
    price = float(row['price'])
    supplier = row['supplier']
    info = supplier_info.get(supplier, {'country': 'Unknown', 'discount': 0})

    return {
        'index': counter['n'],
        'product_code': row['category'][:3].upper() + '-' + row['sku'].split('-')[1],
        'product': {
            'name': row['product_name'].upper(),
            'category': row['category'],
        },
        'supplier': {
            'name': supplier,
            'country': info['country'],
        },
        'pricing': {
            'original': price,
            'discounted': round(price * (1 - info['discount']), 2),
            'discount_pct': str(int(info['discount'] * 100)) + '%',
            'currency': 'USD',
        },
        'inventory': {
            'quantity': qty,
            'value': round(price * qty, 2),
        },
    }
```

**Output:**
```json
[
  {
    "index": 1,
    "product_code": "ELE-001",
    "product": {"name": "WIRELESS MOUSE", "category": "Electronics"},
    "supplier": {"name": "TechCorp", "country": "USA"},
    "pricing": {"original": 29.99, "discounted": 25.49, "discount_pct": "15%", "currency": "USD"},
    "inventory": {"quantity": 150, "value": 4498.5}
  },
  {
    "index": 2,
    "product_code": "ELE-002",
    "product": {"name": "USB-C HUB", "category": "Electronics"},
    "supplier": {"name": "TechCorp", "country": "USA"},
    "pricing": {"original": 49.99, "discounted": 42.49, "discount_pct": "15%", "currency": "USD"},
    "inventory": {"quantity": 85, "value": 4249.15}
  },
  {
    "index": 3,
    "product_code": "ELE-004",
    "product": {"name": "MECHANICAL KEYBOARD", "category": "Electronics"},
    "supplier": {"name": "KeyMaster", "country": "Japan"},
    "pricing": {"original": 89.99, "discounted": 85.49, "discount_pct": "5%", "currency": "USD"},
    "inventory": {"quantity": 200, "value": 17998.0}
  },
  {
    "index": 4,
    "product_code": "FUR-005",
    "product": {"name": "MONITOR ARM", "category": "Furniture"},
    "supplier": {"name": "OfficePro", "country": "Germany"},
    "pricing": {"original": 129.99, "discounted": 116.99, "discount_pct": "10%", "currency": "USD"},
    "inventory": {"quantity": 45, "value": 5849.55}
  }
]
```

> **Note:** Standing Desk (stock_qty: 12) was filtered out because it has fewer than 20 units.

## Project Structure

```
DataIntegrator/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── manage.py
├── converter/                      # Django project settings
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/mapping/                   # Main app
│   ├── models.py                   # ConversionJob model
│   ├── executor.py                 # Sandboxed Python code execution
│   ├── views_file.py               # File upload + job management views
│   ├── urls.py
│   └── maps/
│       ├── json_to_csv_file.py     # JSON-to-CSV mapper
│       └── csv_to_json_file.py     # CSV-to-JSON mapper
├── templates/
│   └── index.html                  # Single-page UI
├── media/                          # Uploaded and converted files
│   └── conversions/<job_id>/
│       ├── input/                  # Original uploaded files
│       └── output/                 # Converted output files
└── test_data/                      # Sample test files
```

## API Endpoints

### Convert

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mapping/file/json-to-csv/` | Upload JSON file + apply_rules code, get CSV |
| `POST` | `/api/mapping/file/csv-to-json/` | Upload CSV file + apply_rules code, get JSON |

#### JSON to CSV

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | JSON file (`.json`) |
| `function_name` | string | No | User-given name for the rule function |
| `rules_code` | string | No | Python code with `def apply_rules(row):` |
| `delimiter` | string | No | CSV delimiter (default: `,`) |
| `quote_data` | bool | No | Quote data fields (default: `true`) |
| `quote_header` | bool | No | Quote header row (default: `false`) |

**Example:**

```bash
curl -X POST http://localhost:8000/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json" \
  -F "function_name=uppercase_names" \
  -F "rules_code=def apply_rules(row):
    row['name'] = row['name'].upper()
    return row"
```

#### CSV to JSON

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | CSV file (`.csv`) |
| `function_name` | string | No | User-given name for the rule function |
| `rules_code` | string | No | Python code with `def apply_rules(row):` |
| `delimiter` | string | No | CSV delimiter (default: `,`) |

**Example:**

```bash
curl -X POST http://localhost:8000/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/products.csv" \
  -F "function_name=type_cast" \
  -F "rules_code=def apply_rules(row):
    row['price'] = float(row['price'])
    row['in_stock'] = row['in_stock'] == 'true'
    return row"
```

> **Note:** CSV values are always strings. Use `int()`, `float()`, or comparison to convert types in your `apply_rules` function.

### Job Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mapping/file/jobs/` | List all conversion jobs |
| `GET` | `/api/mapping/file/jobs/<job_id>/` | Get job detail with logs |
| `GET` | `/api/mapping/file/jobs/<job_id>/download/` | Download the converted output file |

**Query filters for job list:** `?status=completed`, `?status=failed`, `?direction=csv_to_json`

### UI

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI with file upload, code editor, and preview |
