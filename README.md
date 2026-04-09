# Data Integrator — JSON & CSV Converter

A Django REST Framework application that converts between **JSON and CSV** formats using **user-defined Python rule functions**, plus an **interactive JSON Transform** tool with natural-language rules. Users upload a file, define transformations visually or in code, and get the converted output with a live preview.

**Features:**
- **JSON to CSV** — Upload a JSON file (array of objects), get a CSV file
- **CSV to JSON** — Upload a CSV file, get a JSON file (array of objects)
- **JSON Transform** — Upload JSON, apply natural-language rules (uppercase, filter, sort, rename, create columns), preview before/after in spreadsheet grids

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

The app has three tabs: **Convert**, **JSON Transform**, and **History**.

### Convert Tab

1. **Select direction** — JSON to CSV or CSV to JSON
2. **Upload** a file (JSON or CSV depending on direction)
3. **Preview** the first 5 rows in a data table
4. **Define rules** using either:
   - **Simple mode** — A visual editor with five sections:
     - **Variables** (yellow) — Click "+ Add Variable" to define shared variables (counters, lookup dicts, constants) placed **above** `def apply_rules`. Shared across all rows.
     - **Local Variables** (green) — Click "+ Add Local Variable" to define variables **inside** `apply_rules` at the top of the function body. Created fresh per row. For things like `price = float(row['price'])` that you reference later in multiple lines.
     - **Column rules** — One code input per detected column with context-aware placeholders (e.g., `row['name'] = str(row['name']).upper()`).
     - **Additional Rules** — Click "+ Add Line" for extra single-line rules (new columns, filters, counter increments, etc.).
     - **Code Block** — A multi-line code editor for `for` loops, `if/else` blocks, and any complex logic that runs inside `apply_rules`. Supports Tab key for indentation.
     All inputs are assembled into a complete `def apply_rules(row):` function automatically.
   - **Advanced mode** — A full code editor where you write the `apply_rules` function directly. Switching from Simple to Advanced syncs the generated code into the editor.
5. **Convert** and preview the output
6. **Download** the output file

### JSON Transform Tab

1. **Upload** a JSON file — data appears in a spreadsheet-like grid
2. **Write natural-language rules** in the rule editor (one per line), e.g.:
   - `uppercase name`
   - `filter age > 18`
   - `sort by salary desc`
   - `rename first_name to name`
   - `create full_name = first_name + last_name`
3. **Apply Rules** — transformed data appears in a second grid below
4. View execution logs showing what each rule did

### History Tab

- Browse all past conversion jobs with status, download links, and filters

---

### Execution Flow (Function-Level)

#### Convert Tab — Full Execution Flow

```
Browser (index.html)
  │
  ├─▶ User uploads file
  │     └─▶ handleFile(file)                          [client-side]
  │           ├─▶ parseJSON(text, 5) or parseCSV(text, 5)
  │           ├─▶ showPreview(headers, rows)
  │           └─▶ renderColumnRules(headers)
  │
  ├─▶ User defines rules (Simple or Advanced mode)
  │     └─▶ generateRulesCode()                       [client-side]
  │           ├─▶ Collects global variable definitions (#variables-list .var-row)
  │           ├─▶ Collects local variable definitions (#local-vars-list .local-var-row)
  │           ├─▶ Collects per-column inputs (.col-rule-input values)
  │           ├─▶ Collects "+ Add Line" inputs (.ncol-expr values)
  │           ├─▶ Collects Code Block textarea (#code-block-editor)
  │           └─▶ Assembles into:
  │                 counter = {'n': 0}    ← global variables (above function)
  │                 lookup = {...}
  │
  │                 def apply_rules(row):
  │                     price = float(row['price'])  ← local variables (top of body)
  │                     name = str(row['name'])
  │
  │                     <column line 1>   ← column rules + add lines
  │                     <column line 2>
  │                     <add line 1>
  │
  │                     for col in [...]: ← code block (loops, if/else)
  │                         row[col] = ...
  │                     return row
  │
  ├─▶ User clicks "Convert"
  │     └─▶ POST /api/mapping/file/json-to-csv/       [or csv-to-json]
  │           Body: FormData { file, rules_code, function_name, delimiter, ... }
  │
  └─▶ Server processes request
        │
        ├─▶ FileUploadJsonToCsvView.post()             [views_file.py]
        │     or FileUploadCsvToJsonView.post()
        │     ├─▶ Validates file extension
        │     ├─▶ Creates ConversionJob record          [models.py]
        │     ├─▶ Saves input file to media/conversions/<job_id>/input/
        │     └─▶ Calls mapper:
        │
        ├─▶ json_to_csv_file_mapper(content, rules_code, ...)  [maps/json_to_csv_file.py]
        │     or csv_to_json_file_mapper(content, rules_code, ...)  [maps/csv_to_json_file.py]
        │     ├─▶ Parses input (json.loads or csv.DictReader)
        │     ├─▶ _collect_all_keys(data) — gets column names
        │     └─▶ If rules_code provided:
        │           │
        │           └─▶ execute_rules(data, rules_code, logs)  [executor.py]
        │                 ├─▶ validate_code(code)
        │                 │     ├─▶ Checks BLOCKED_PATTERNS (open, eval, exec, __dunder__, ...)
        │                 │     ├─▶ _validate_imports(code)
        │                 │     │     └─▶ Allows: datetime, math, json, re, uuid, ...
        │                 │     │         Blocks: os, sys, subprocess, shutil, ...
        │                 │     └─▶ Checks "def apply_rules(" exists
        │                 │
        │                 ├─▶ _preload_imports(code, safe_globals)
        │                 │     └─▶ Loads allowed modules into sandbox namespace
        │                 │
        │                 ├─▶ exec(code, safe_globals)
        │                 │     └─▶ Defines apply_rules() + top-level vars (e.g. counter)
        │                 │
        │                 ├─▶ transform_fn = safe_globals["apply_rules"]
        │                 │
        │                 └─▶ For each row in data:
        │                       ├─▶ row_copy = deepcopy(row)
        │                       ├─▶ result = transform_fn(row_copy)
        │                       ├─▶ result is None → row filtered out
        │                       ├─▶ result is dict → added to output
        │                       └─▶ Exception → error logged, row skipped
        │
        ├─▶ Mapper builds output (CSV string or JSON string)
        ├─▶ Saves output file to media/conversions/<job_id>/output/
        ├─▶ Updates ConversionJob (status, rows_processed, logs)
        └─▶ Returns JSON response → Browser shows result + download link
```

#### JSON Transform Tab — Full Execution Flow

```
Browser (index.html — JSON Transform tab)
  │
  ├─▶ User uploads JSON file
  │     └─▶ POST /api/mapping/transform/upload/
  │           │
  │           └─▶ TransformUploadView.post()           [views_file.py]
  │                 ├─▶ Validates .json extension
  │                 ├─▶ json.loads(content) → list of dicts
  │                 ├─▶ _data_preview(data) → columns, rows, stats
  │                 └─▶ Returns { preview, data }
  │
  ├─▶ Browser renders original data in spreadsheet grid
  │     └─▶ tfRenderGrid(container, columns, rows)     [client-side]
  │
  ├─▶ User writes rules and clicks "Apply Rules"
  │     └─▶ POST /api/mapping/transform/apply/
  │           Body: { "data": [...], "rules": "uppercase name\nfilter age > 18" }
  │           │
  │           └─▶ TransformApplyView.post()            [views_file.py]
  │                 │
  │                 └─▶ execute_natural_rules(data, rules_text)  [executor.py]
  │                       ├─▶ Deep-copies data
  │                       ├─▶ Splits rules_text into lines (skips # comments, blanks)
  │                       └─▶ For each rule line:
  │                             ├─▶ Matches against _NL_HANDLERS (regex patterns)
  │                             │
  │                             ├─▶ Text:    _nl_uppercase, _nl_lowercase, _nl_titlecase,
  │                             │            _nl_trim, _nl_replace, _nl_regex_replace, _nl_concat
  │                             │
  │                             ├─▶ Filter:  _nl_filter_word, _nl_filter_symbolic
  │                             │            Uses _FILTER_OPS: equals, !=, contains,
  │                             │            startswith, endswith, >, >=, <, <=
  │                             │
  │                             ├─▶ Sort:    _nl_sort (multi-column, asc/desc)
  │                             │            Uses _sort_key() for numeric-aware sorting
  │                             │
  │                             ├─▶ Column:  _nl_rename (order-preserving via _rename_key_in_place),
  │                             │            _nl_remove, _nl_duplicate, _nl_create
  │                             │
  │                             ├─▶ Reorder: _nl_reorder (listed first, unlisted keep order)
  │                             │
  │                             └─▶ No match → ValueError
  │
  └─▶ Browser renders transformed data + logs
        ├─▶ tfRenderGrid(afterGrid, columns, rows)     [client-side]
        └─▶ tfToast("Transform complete — N rows", "success")
```

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
- The browser renders three tabs: **Convert** (active), **JSON Transform**, and **History**

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
       ├─▶ renderColumnRules(headers) — renders per-column visual code inputs
       └─▶ Reveals Step 2 (preview) and Step 3 (rules editor) cards
            Enables the Convert button
```

**What happens:**
- No API call is made — this is entirely client-side
- `handleFile()` — handles file selection from click or drag-drop
- `parseJSON()` — best-effort JSON parse for large files (reads only first 64KB)
- `parseCSV()` — parses CSV text by splitting lines and handling quoted fields
- `parseCSVLine()` — handles CSV quoting (double-quote escaping, delimiters inside quotes)
- `showPreview()` — builds an HTML table showing column headers and up to 5 rows
- `renderColumnRules()` — renders one code input per column with context-aware placeholders (e.g., `row['name'] = str(row['name']).upper()` for a column named `name`)

---

#### Step 3: Define Transform Rules (Client-Side Only)

```
User defines rules in Simple mode or Advanced mode
  │
  ├─▶ Simple mode (visual editor):
  │     ├─▶ "Variables" section (yellow) with "+ Add Variable"
  │     │   Define variables ABOVE def apply_rules (shared across rows)
  │     │   For counters, lookup dicts, constants
  │     ├─▶ "Local Variables" section (green) with "+ Add Local Variable"
  │     │   Define variables INSIDE apply_rules at the top (per-row)
  │     │   For price = float(row['price']), name = str(row['name']), etc.
  │     ├─▶ One code input per detected column
  │     │   Each input has a placeholder like: row['name'] = str(row['name']).upper()
  │     ├─▶ "Additional Rules" section with "+ Add Line"
  │     │   For new columns, filters, or any extra single-line Python
  │     ├─▶ "Code Block" textarea for multi-line code
  │     │   For loops, if/else blocks, complex logic (Tab key supported)
  │     └─▶ generateRulesCode() assembles everything:
  │           Global Variables → above the function
  │           def apply_rules(row):
  │               Local Variables → top of function body
  │               Column inputs + Add Lines → body
  │               Code Block → body
  │               return row
  │
  ├─▶ Advanced mode (code editor):
  │     ├─▶ Full textarea with def apply_rules(row): function
  │     ├─▶ Switching from Simple → Advanced syncs generated code into the editor
  │     └─▶ Tab key inserts 4 spaces
  │
  ├─▶ Optional: enters a function name (e.g., "clean_products")
  ├─▶ Optional: toggles CSV options (quote data, quote header, delimiter)
  └─▶ Clicks "Convert to CSV" or "Convert to JSON"
```

**What happens:**
- In Simple mode, the editor has five sections:
  - **Variables** (yellow) — Click "+ Add Variable" to define name/value pairs placed **above** `def apply_rules(row):`. Used for counters (`{'n': 0}`), lookup dicts, constants, etc. These are shared across all rows.
  - **Local Variables** (green) — Click "+ Add Local Variable" to define variables **inside** `apply_rules` at the top of the function body. These are created fresh for each row. For extracting values like `price = float(row['price'])` to reference in multiple places below.
  - **Column rules** — One input per detected column with a context-aware placeholder. Type Python code directly (e.g., `row['ID'] = row.pop('sku', '')` to rename, `row.pop('temp', None)` to remove, `row['name'] = str(row['name']).upper()` to transform).
  - **Additional Rules** — Click "+ Add Line" for extra single-line code (new columns, filters, counter increments, etc.)
  - **Code Block** — A multi-line textarea for `for` loops, `if/else` blocks, and complex logic. Supports Tab for indentation. Code is placed inside the function body after single-line rules.
- `generateRulesCode()` assembles: global variables above the function → local variables at the top of the function body → single-line rules + code block → `return row`
- Switching to Advanced mode syncs the full generated code into the editor
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
// In Simple mode, generateRulesCode() assembles per-column inputs into apply_rules code
// In Advanced mode, the code editor value is used directly
const rulesCode = currentMode === 'simple' ? generateRulesCode() : $codeEditor.value;
formData.append('rules_code', rulesCode);
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

`apps/mapping/executor.py` — `execute_rules()`

```
execute_rules(data, code, logs)
  │
  ├─▶ 7a. Validate code — validate_code()
  │     ├─▶ Regex check against BLOCKED_PATTERNS:
  │     │     open(), eval(), exec(), compile(),
  │     │     globals(), locals(), getattr(), setattr(), delattr(),
  │     │     __dunder__, subprocess
  │     ├─▶ Validate imports — _validate_imports()
  │     │     ├─▶ Parse all import/from lines
  │     │     ├─▶ Block: os, sys, subprocess, shutil, socket, ctypes, signal, pickle
  │     │     └─▶ Allow: datetime, math, json, re, string, decimal, collections,
  │     │          itertools, functools, uuid, hashlib, base64, urllib.parse,
  │     │          html, textwrap, random
  │     └─▶ Check "def apply_rules(" exists in code
  │         Raises ValueError if any check fails
  │
  ├─▶ 7b. Auto-inject modules + execute code in sandbox
  │     ├─▶ _auto_inject_modules(safe_globals)
  │     │   Pre-loads ALL allowed modules + common members into namespace
  │     │   So datetime.now(), math.sqrt(), uuid.uuid4() etc. work without imports
  │     ├─▶ _preload_imports(code, safe_globals)
  │     │   Also handles explicit import/from statements for aliases
  │     ├─▶ Import lines are stripped from code before exec
  │     ├─▶ safe_globals = {"__builtins__": SAFE_BUILTINS + __import__}
  │     │   SAFE_BUILTINS: str, int, float, bool, len, list, dict, tuple,
  │     │   set, round, min, max, abs, sum, any, all, enumerate, zip,
  │     │   sorted, reversed, range, map, filter, isinstance, type, print
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
  ├─▶ On success → showSuccess(data)
  │     ├─▶ Shows green "Completed" badge
  │     ├─▶ Shows stats: rows processed, columns count, output filename
  │     ├─▶ Shows CSV output in dark-themed preview box
  │     ├─▶ Shows "Download CSV" button (links to download endpoint)
  │     └─▶ Shows collapsible processing logs
  │
  └─▶ On error → showError(data)
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
  └─▶ loadJobs()
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

#### JSON Transform Tab Workflow

The JSON Transform tab provides a separate workflow using natural-language rules instead of Python code.

```
1. User clicks "JSON Transform" tab
   │
   └─▶ Shows upload zone, rule editor (hidden until upload)

2. User uploads a JSON file
   │
   └─▶ POST /api/mapping/transform/upload/
        │
        ├─▶ TransformUploadView (views_file.py)
        │     ├─▶ Validates file extension (.json)
        │     ├─▶ Parses JSON into list of dicts
        │     └─▶ Returns preview (columns, rows, stats) + raw data
        │
        └─▶ Frontend renders:
              ├─▶ Original data in spreadsheet grid (before)
              └─▶ Rule editor + reference panel

3. User writes rules and clicks "Apply Rules" (or Ctrl+Enter)
   │
   └─▶ POST /api/mapping/transform/apply/
        │
        Body: {"data": [...], "rules": "uppercase name\nfilter age > 18"}
        │
        ├─▶ TransformApplyView (views_file.py)
        │     └─▶ execute_natural_rules(data, rules_text)  (executor.py)
        │           │
        │           ├─▶ Deep-copies data
        │           ├─▶ Parses each line against registered rule patterns
        │           ├─▶ Applies rules sequentially (each transforms the data)
        │           └─▶ Returns (transformed_data, logs)
        │
        └─▶ Frontend renders:
              ├─▶ Transformed data in spreadsheet grid (after)
              ├─▶ Execution logs (terminal-style panel)
              └─▶ Toast notification (success/error)
```

**The natural-language rule engine** (`execute_natural_rules` in `executor.py`) uses a pattern-registration system. Each rule type (uppercase, filter, sort, etc.) is registered with a regex pattern. Rules are matched and dispatched to handler functions that operate on plain Python dicts — no pandas or external dependencies required.

---

### File and Function Summary

| Step | File | Function / Class | Purpose |
|------|------|-----------------|---------|
| 1 | `converter/urls.py:10` | `TemplateView` | Serve the web UI |
| 1b | `templates/index.html` | direction switching handler | Switch between JSON-to-CSV and CSV-to-JSON |
| 2 | `templates/index.html` | `handleFile()` | Handle file upload (client-side) |
| 2 | `templates/index.html` | `parseJSON()` | Parse JSON for preview (client-side) |
| 2 | `templates/index.html` | `parseCSV()` | Parse CSV for preview (client-side) |
| 2 | `templates/index.html` | `showPreview()` | Render data preview table (client-side) |
| 2 | `templates/index.html` | `renderColumnRules()` | Render per-column visual code inputs (client-side) |
| 3 | `templates/index.html` | `generateRulesCode()` | Assemble visual inputs into `def apply_rules(row):` |
| 4 | `templates/index.html` | `$btnConvert click` | Send POST request with FormData |
| 5 | `apps/mapping/views_file.py` | `FileUploadJsonToCsvView` | Handle JSON upload, create job, call mapper |
| 5 | `apps/mapping/views_file.py` | `FileUploadCsvToJsonView` | Handle CSV upload, create job, call mapper |
| 5 | `apps/mapping/models.py` | `ConversionJob` | Database model for job tracking |
| 6a | `apps/mapping/maps/json_to_csv_file.py` | `json_to_csv_file_mapper()` | Parse JSON, apply rules, build CSV |
| 6b | `apps/mapping/maps/csv_to_json_file.py` | `csv_to_json_file_mapper()` | Parse CSV, apply rules, build JSON |
| 7 | `apps/mapping/executor.py` | `validate_code()` | Security validation of user code |
| 7 | `apps/mapping/executor.py` | `execute_rules()` | Sandbox execute apply_rules on each row |
| 7 | `apps/mapping/executor.py` | `execute_natural_rules()` | Parse and apply natural-language rules (JSON Transform tab) |
| 8 | `templates/index.html` | `showSuccess()` | Display result with output preview |
| 8 | `templates/index.html` | `showError()` | Display error message |
| 9 | `apps/mapping/views_file.py` | `ConversionJobDownloadView` | Serve output file download |
| 10 | `apps/mapping/views_file.py` | `ConversionJobListView` | List all conversion jobs |
| 10 | `apps/mapping/views_file.py` | `ConversionJobDetailView` | Get single job details |
| 10 | `templates/index.html` | `loadJobs()` | Fetch and render job history (client-side) |
| — | `apps/mapping/views_file.py` | `TransformUploadView` | Upload JSON, return table preview (JSON Transform tab) |
| — | `apps/mapping/views_file.py` | `TransformApplyView` | Apply natural-language rules, return transformed preview |

### Apply Rules Function

Users define row transformations via the **visual editor** (Simple mode) or by writing a `def apply_rules(row):` function directly (Advanced mode). In Simple mode, each column gets a single code input where you type the Python line for that column. The app assembles all inputs into a `def apply_rules(row):` function automatically.

The function receives each row as a Python dict and returns the modified dict. Return `None` to filter a row out.

#### Visual Editor Examples (Simple Mode)

The Simple mode has five sections:

1. **Variables** (yellow) — Click "+ Add Variable" to define variables that go **above** `def apply_rules(row):`. These are shared across all rows (counters, lookup dicts, constants).
2. **Local Variables** (green) — Click "+ Add Local Variable" to define variables **inside** `apply_rules` at the top of the function body. These are created fresh for each row. Use for extracting values like `price = float(row['price'])` that you reference in multiple places below.
3. **Column rules** — One code input per detected column. Type the Python line for that column.
4. **Additional Rules** — Click "+ Add Line" for extra single-line code (new columns, filters, etc.).
5. **Code Block** — A multi-line code editor for `for` loops, `if/else` blocks, and complex logic. Supports Tab key. Code runs inside `apply_rules` after single-line rules.

When you upload a file with columns `sku`, `product_name`, `price`, `stock_qty`, `supplier`, each column shows an input with a placeholder. You type actual Python code:

**Example with all five sections:**

| Section | Name | Value / Code |
|---|---|---|
| + Add Variable | `counter` | `{'n': 0}` |
| + Add Variable | `brand_country` | `{'TechBrand': 'USA', 'SoundMax': 'Japan', 'WristTech': 'South Korea'}` |
| + Add Local Variable | `price` | `float(row['price'])` |
| + Add Local Variable | `supplier` | `row.get('supplier', '')` |
| Column: `sku` | | `row['ID'] = row.pop('sku', '')` |
| Column: `product_name` | | `row['product_name'] = row['product_name'].upper()` |
| Column: `price` | | *(leave empty — no change)* |
| Column: `stock_qty` | | `row.pop('stock_qty', None)` |
| Column: `supplier` | | `row['vendor'] = row.pop('supplier', '')` |
| + Add Line | | `counter['n'] += 1` |
| + Add Line | | `row['serial_no'] = counter['n']` |
| + Add Line | | `row['country'] = brand_country.get(supplier, 'Unknown')` |
| + Add Line | | `row['tax'] = round(price * 0.08, 2)` |
| + Add Line | | `row['total'] = round(price * 1.08, 2)` |
| + Add Line | | `if price < 10: return None` |

This generates:
```python
counter = {'n': 0}
brand_country = {'TechBrand': 'USA', 'SoundMax': 'Japan', 'WristTech': 'South Korea'}

def apply_rules(row):
    price = float(row['price'])
    supplier = row.get('supplier', '')

    row['ID'] = row.pop('sku', '')
    row['product_name'] = row['product_name'].upper()
    row.pop('stock_qty', None)
    row['vendor'] = row.pop('supplier', '')
    counter['n'] += 1
    row['serial_no'] = counter['n']
    row['country'] = brand_country.get(supplier, 'Unknown')
    row['tax'] = round(price * 0.08, 2)
    row['total'] = round(price * 1.08, 2)
    if price < 10: return None
    return row
```

> Notice how `price` and `supplier` local variables are used in multiple lines below — without local variables, you'd need to write `float(row['price'])` every time.

**Common variable examples (Variables — above function, yellow):**

| Name | Value | Use in column/line |
|---|---|---|
| `x` | `'abc'` | `row['prefix'] = x` |
| `counter` | `{'n': 0}` | `counter['n'] += 1; row['serial'] = counter['n']` |
| `lookup` | `{'A': 'Alpha', 'B': 'Beta'}` | `row['label'] = lookup.get(row['code'], 'Unknown')` |
| `tax_rate` | `0.08` | `row['tax'] = round(price * tax_rate, 2)` |
| `prefix` | `'PRD'` | `row['sku'] = prefix + '-' + str(row['id']).zfill(4)` |

**Common local variable examples (Local Variables — inside function, green):**

| Name | Value | Why |
|---|---|---|
| `price` | `float(row['price'])` | Use `price` instead of `float(row['price'])` in multiple lines |
| `name` | `str(row['name']).strip()` | Clean once, reference everywhere |
| `qty` | `int(row['stock_qty'])` | Cast once, use in calculations |
| `dept` | `row.get('department', '')` | Short alias for a long column name |
| `is_active` | `row.get('is_active') == 'true'` | Parse boolean once, use in filters |

**Code Block examples (for loops, if/else, sequences):**

The Code Block textarea supports multi-line Python with proper indentation. Write code as you would inside a function — it gets placed inside `def apply_rules(row):`.

**Uppercase multiple columns with a for loop:**
```python
# Write this in the Code Block textarea:
for col in ['name', 'brand', 'category']:
    row[col] = str(row[col]).upper()
```

**If/else to set a tier label:**
```python
if float(row['price']) > 500:
    row['tier'] = 'Premium'
elif float(row['price']) > 100:
    row['tier'] = 'Mid-Range'
else:
    row['tier'] = 'Budget'
```

**Remove multiple columns with a for loop:**
```python
for col in ['temp_id', 'internal_notes', 'debug_flag']:
    row.pop(col, None)
```

**Rename multiple columns with a dict:**
```python
renames = {'name': 'product_name', 'brand': 'manufacturer', 'price': 'unit_price'}
for old, new in renames.items():
    if old in row:
        row[new] = row.pop(old)
```

**Set default values for multiple columns:**
```python
defaults = {'category': 'Unknown', 'status': 'active', 'currency': 'USD'}
for col, default in defaults.items():
    if not row.get(col):
        row[col] = default
```

**Reorder columns after transformations:**
```python
order = ['serial', 'id', 'product_name', 'manufacturer', 'price', 'tier']
row = {k: row[k] for k in order if k in row}
```

**Full example combining Variables + Column rules + Add Lines + Code Block:**

| Section | Name | Value / Code |
|---|---|---|
| + Add Variable | `counter` | `{'n': 0}` |
| + Add Variable | `tax_rate` | `0.08` |
| Column: `sku` | | `row['ID'] = row.pop('sku', '')` |
| Column: `stock_qty` | | `row.pop('stock_qty', None)` |
| + Add Line | | `counter['n'] += 1` |
| + Add Line | | `row['serial'] = counter['n']` |

Code Block:
```python
for col in ['product_name', 'supplier']:
    row[col] = str(row[col]).strip().upper()

row['tax'] = round(float(row['price']) * tax_rate, 2)
row['total'] = round(float(row['price']) * (1 + tax_rate), 2)

if float(row['price']) > 100:
    row['tier'] = 'Premium'
else:
    row['tier'] = 'Standard'

order = ['serial', 'ID', 'product_name', 'supplier', 'price', 'tax', 'total', 'tier']
row = {k: row[k] for k in order if k in row}
```

This generates:
```python
counter = {'n': 0}
tax_rate = 0.08

def apply_rules(row):
    row['ID'] = row.pop('sku', '')
    row.pop('stock_qty', None)
    counter['n'] += 1
    row['serial'] = counter['n']

    for col in ['product_name', 'supplier']:
        row[col] = str(row[col]).strip().upper()

    row['tax'] = round(float(row['price']) * tax_rate, 2)
    row['total'] = round(float(row['price']) * (1 + tax_rate), 2)

    if float(row['price']) > 100:
        row['tier'] = 'Premium'
    else:
        row['tier'] = 'Standard'

    order = ['serial', 'ID', 'product_name', 'supplier', 'price', 'tax', 'total', 'tier']
    row = {k: row[k] for k in order if k in row}
    return row
```

**Simple example (no code block) — rename, transform, remove:**

| Section | Code |
|---|---|
| Column: `sku` | `row['ID'] = row.pop('sku', '')` |
| Column: `product_name` | `row['product_name'] = row['product_name'].upper()` |
| Column: `stock_qty` | `row.pop('stock_qty', None)` |
| Column: `supplier` | `row['vendor'] = row.pop('supplier', '')` |
| + Add Line | `row['tax'] = round(float(row['price']) * 0.08, 2)` |
| + Add Line | `if float(row['price']) < 10: return None` |

This generates:
```python
def apply_rules(row):
    row['ID'] = row.pop('sku', '')
    row['product_name'] = row['product_name'].upper()
    row.pop('stock_qty', None)
    row['vendor'] = row.pop('supplier', '')
    row['tax'] = round(float(row['price']) * 0.08, 2)
    if float(row['price']) < 10: return None
    return row
```

**Filter rows (use "+ Add Line" or any column input):**

Type `return None` to skip rows that match a condition. The logic is: if the condition is true, return None (skip the row).

| Filter type | Code to type in "+ Add Line" |
|---|---|
| Numeric comparison | `if float(row['price']) < 100: return None` |
| Exact match | `if row['brand'] != 'TechBrand': return None` |
| Contains text | `if 'Smart' not in str(row['name']): return None` |
| Starts with | `if not str(row['name']).startswith('Pro'): return None` |
| Ends with | `if not str(row['email']).endswith('.com'): return None` |
| Boolean field | `if not row.get('in_stock'): return None` |
| Value in list | `if row['status'] not in ['active', 'pending']: return None` |
| Price range (keep) | `if not (50 <= float(row['price']) <= 300): return None` |
| AND condition | `if not (row['brand'] == 'TechBrand' and float(row['price']) > 500): return None` |
| OR condition | `if not (row['brand'] == 'SoundMax' or float(row['price']) > 1000): return None` |

**Add columns (use "+ Add Line"):**

| What you want | Code to type in "+ Add Line" |
|---|---|
| Static value | `row['currency'] = 'USD'` |
| Computed | `row['tax'] = round(float(row['price']) * 0.08, 2)` |
| Concatenate | `row['display'] = str(row['name']) + ' by ' + str(row['brand'])` |
| Conditional | `row['tier'] = 'Premium' if float(row['price']) >= 500 else 'Standard'` |
| Based on existing | `row['serial_no'] = int(row.get('number', 0)) + 1` |

**Add auto-incrementing serial number (requires Advanced mode):**

An auto-increment counter needs a shared variable above `def apply_rules`, so it must be done in Advanced mode:

```python
counter = {'n': 0}

def apply_rules(row):
    counter['n'] += 1
    row['serial_no'] = counter['n']
    return row
# serial_no: 1, 2, 3, 4, 5
```

| Variation | Change |
|---|---|
| Start from 0 | `counter = {'n': -1}` |
| Start from 100 | `counter = {'n': 99}` |
| Padded (001, 002) | `row['serial_no'] = str(counter['n']).zfill(3)` |
| With prefix | `row['serial_no'] = 'SN-' + str(counter['n']).zfill(4)` |

> **Note:** A plain variable like `counter = 0` won't work because Python closures can't reassign outer variables without `nonlocal`. Use a dict — its values can be mutated from inside the function.

**Add datetime columns (no import needed — auto-available):**

Use in Simple mode ("+ Add Line"), Advanced mode, or anywhere — no import required:

```python
# Simple mode: just type these in "+ Add Line" inputs
row['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
row['date_only'] = datetime.now().strftime('%d/%m/%Y')
row['tomorrow'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
```

| Format | Code | Output |
|---|---|---|
| Full datetime | `datetime.now().strftime('%Y-%m-%d %H:%M:%S')` | `2026-04-09 14:30:00` |
| Date only | `datetime.now().strftime('%Y-%m-%d')` | `2026-04-09` |
| DD/MM/YYYY | `datetime.now().strftime('%d/%m/%Y')` | `09/04/2026` |
| ISO 8601 | `datetime.now().isoformat()` | `2026-04-09T14:30:00.123456` |
| Time only | `datetime.now().strftime('%H:%M:%S')` | `14:30:00` |
| Custom | `datetime.now().strftime('%b %d, %Y')` | `Apr 09, 2026` |
| Tomorrow | `(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')` | `2026-04-10` |
| Unix timestamp | `str(int(datetime.now().timestamp()))` | `1775916600` |

**Other auto-available modules (no import needed):**

Use directly in Simple mode or Advanced mode — they're all pre-loaded:

```python
# All of these work without any import statement:
def apply_rules(row):
    row['uid'] = str(uuid.uuid4())[:8]
    row['price_sqrt'] = round(math.sqrt(float(row['price'])), 2)
    row['hash'] = hashlib.md5(str(row['id']).encode()).hexdigest()[:8]
    row['meta'] = json.dumps({'source': 'api', 'version': 2})
    row['clean_name'] = re.sub(r'[^a-zA-Z0-9 ]', '', str(row['name']))
    row['rand'] = random.randint(1, 100)
    row['b64'] = base64.b64encode(str(row['id']).encode()).decode()
    return row
```

Auto-available: `datetime`, `timedelta`, `date`, `time`, `timezone`, `math`, `json`, `re`, `string`, `decimal`, `Decimal`, `collections`, `OrderedDict`, `defaultdict`, `Counter`, `namedtuple`, `itertools`, `functools`, `uuid`, `hashlib`, `base64`, `html`, `textwrap`, `random`

#### JSON Transform Tab — Natural-Language Rules

The JSON Transform tab uses a different syntax — plain English rules, one per line:

**Filter examples:**

| Rule | Effect |
|---|---|
| `filter price > 100` | Keep rows where price > 100 |
| `filter brand equals TechBrand` | Keep rows where brand is TechBrand |
| `filter brand != Unknown` | Keep rows where brand is not Unknown |
| `filter name contains Smart` | Keep rows where name contains "Smart" |
| `filter name startswith Pro` | Keep rows where name starts with "Pro" |
| `filter email endswith .com` | Keep rows where email ends with ".com" |
| `filter age >= 18` | Keep rows where age >= 18 |
| `filter stock_qty < 50` | Keep rows where stock_qty < 50 |

**Other rule examples:**

| Rule | Effect |
|---|---|
| `uppercase name` | Uppercase the name column |
| `lowercase email` | Lowercase the email column |
| `titlecase city` | Title-case the city column |
| `trim name` | Strip whitespace from name |
| `sort by salary desc` | Sort by salary descending |
| `sort by dept asc, salary desc` | Multi-column sort |
| `rename first_name to name` | Rename a column |
| `remove temp_id` | Remove a column |
| `duplicate price as original_price` | Duplicate a column |
| `create full_name = first + last` | Concatenate columns (string) |
| `create bonus = salary * 0.1` | Arithmetic expression |
| `replace in name Pro with Professional` | Replace text |
| `concat first last as full_name` | Concatenate with space |
| `reorder id, name, price` | Set column order (unlisted go to end) |

#### Advanced Mode Examples

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

**Auto-available modules** — these are pre-loaded automatically. **No import statement needed.** Just use them directly:

`datetime`, `timedelta`, `date`, `time`, `timezone`, `math`, `json`, `re`, `string`, `decimal`, `Decimal`, `collections`, `OrderedDict`, `defaultdict`, `Counter`, `namedtuple`, `itertools`, `functools`, `uuid`, `hashlib`, `base64`, `html`, `textwrap`, `random`

```python
# No imports needed — just use directly:
def apply_rules(row):
    row['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row['tomorrow'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    row['price_sqrt'] = round(math.sqrt(float(row['price'])), 2)
    row['uid'] = str(uuid.uuid4())[:8]
    row['meta'] = json.dumps({'source': 'api'})
    row['hash'] = hashlib.md5(str(row['id']).encode()).hexdigest()[:8]
    row['clean'] = re.sub(r'[^a-zA-Z0-9 ]', '', str(row['name']))
    return row
```

> **Note:** `datetime` is the `datetime.datetime` class directly, so `datetime.now()` works without `datetime.datetime.now()`. Similarly, `timedelta`, `date`, `time`, `timezone`, `Decimal`, `OrderedDict`, `defaultdict`, `Counter`, `namedtuple` are all directly available.

Explicit `import` and `from ... import` statements also still work for backward compatibility or aliasing:

```python
from datetime import datetime as dt
import math as m

def apply_rules(row):
    row['ts'] = dt.now().isoformat()
    row['sqrt'] = m.sqrt(float(row['price']))
    return row
```

**Blocked for security:** `open`, `eval`, `exec`, `compile`, `__dunder__` attributes, `os`, `sys`, `subprocess`, `shutil`, `socket`, `ctypes`, `signal`, `pickle`, and any module not in the allowed list

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

All text transforms can be used in Simple mode (type in the column's input), Advanced mode (inside `def apply_rules`), or JSON Transform tab (natural-language rules).

**Uppercase a text field:**

| Mode | Code |
|---|---|
| Simple (name input) | `row['name'] = str(row['name']).upper()` |
| JSON Transform | `uppercase name` |

```python
def apply_rules(row):
    row['name'] = str(row['name']).upper()
    return row
# "Laptop Pro" → "LAPTOP PRO"
```

**Lowercase a text field:**

| Mode | Code |
|---|---|
| Simple (brand input) | `row['brand'] = str(row['brand']).lower()` |
| JSON Transform | `lowercase brand` |

```python
def apply_rules(row):
    row['brand'] = str(row['brand']).lower()
    return row
# "TechBrand" → "techbrand"
```

**Title case:**

| Mode | Code |
|---|---|
| Simple (name input) | `row['name'] = str(row['name']).title()` |
| JSON Transform | `titlecase name` |

```python
def apply_rules(row):
    row['name'] = str(row['name']).title()
    return row
# "wireless earbuds" → "Wireless Earbuds"
```

**Strip whitespace:**

| Mode | Code |
|---|---|
| Simple (name input) | `row['name'] = str(row['name']).strip()` |
| JSON Transform | `trim name` |

```python
def apply_rules(row):
    row['name'] = str(row['name']).strip()
    return row
```

**Replace text in a field:**

| Mode | Code |
|---|---|
| Simple (name input) | `row['name'] = str(row['name']).replace('Pro', 'Professional')` |
| JSON Transform | `replace in name Pro with Professional` |

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

| Mode | Code |
|---|---|
| Simple (+ Add Line) | `row['category'] = 'Electronics'` |
| JSON Transform | Not supported (use Convert tab) |

```python
def apply_rules(row):
    row['category'] = 'Electronics'
    row['currency'] = 'USD'
    return row
```

**Add a computed column:**

| Mode | Code |
|---|---|
| Simple (+ Add Line) | `row['discounted_price'] = round(float(row['price']) * 0.9, 2)` |
| JSON Transform | `create discounted_price = price * 0.9` |

```python
def apply_rules(row):
    row['discounted_price'] = round(float(row['price']) * 0.9, 2)
    return row
# price 1299.99 → discounted_price 1169.99
```

**Add tax and total:**

| Mode | Code |
|---|---|
| Simple (+ Add Line) | `row['tax'] = round(float(row['price']) * 0.08, 2)` |
| Simple (+ Add Line) | `row['total'] = round(float(row['price']) * 1.08, 2)` |
| JSON Transform | `create tax = price * 0.08` then `create total = price * 1.08` |

```python
def apply_rules(row):
    price = float(row['price'])
    row['tax'] = round(price * 0.08, 2)
    row['total'] = round(price * 1.08, 2)
    return row
# price 79.99 → tax 6.40, total 86.39
```

**Add a row number / sequence:**

Auto-increment requires a shared counter variable above `def apply_rules`. In Simple mode, use **"+ Add Variable"** to define it.

| Mode | How |
|---|---|
| Simple | + Add Variable: name=`counter` value=`{'n': 0}`, then + Add Line: `counter['n'] += 1` and `row['row_num'] = counter['n']` |
| Advanced | Define `counter = {'n': 0}` above the function |
| JSON Transform | Not supported (use Convert tab) |

**Simple mode setup:**

| Section | Name | Value / Code |
|---|---|---|
| + Add Variable | `counter` | `{'n': 0}` |
| + Add Line | | `counter['n'] += 1` |
| + Add Line | | `row['row_num'] = counter['n']` |

**Advanced mode:**
```python
counter = {'n': 0}

def apply_rules(row):
    counter['n'] += 1
    row['row_num'] = counter['n']
    return row
# row_num: 1, 2, 3, 4, 5
```

**Variations:**

| What you want | Variable value | Code change |
|---|---|---|
| Start from 0 | `{'n': -1}` | same |
| Start from 100 | `{'n': 99}` | same |
| Padded (001, 002, 003) | `{'n': 0}` | `row['row_num'] = str(counter['n']).zfill(3)` |
| With prefix (SN-0001) | `{'n': 0}` | `row['row_num'] = 'SN-' + str(counter['n']).zfill(4)` |

> **Note:** A plain variable like `counter = 0` won't work because Python closures can't reassign outer integers without `nonlocal`. Use a dict — its values can be mutated from inside the function.

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

**Add a datetime column (Advanced mode — requires import):**
```python
from datetime import datetime

def apply_rules(row):
    row['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return row
# created_at: "2026-04-09 14:30:00"
```

**Add date in multiple formats:**
```python
from datetime import datetime, timedelta

def apply_rules(row):
    now = datetime.now()
    row['date'] = now.strftime('%Y-%m-%d')
    row['date_eu'] = now.strftime('%d/%m/%Y')
    row['date_human'] = now.strftime('%b %d, %Y')
    row['timestamp'] = str(int(now.timestamp()))
    row['tomorrow'] = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    return row
```

---

#### Remove Columns

**Remove a single column:**

| Mode | Code |
|---|---|
| Simple (in_stock input) | `row.pop('in_stock', None)` |
| JSON Transform | `remove in_stock` |

```python
def apply_rules(row):
    row.pop('in_stock', None)
    return row
```

**Remove multiple columns:**

| Mode | Code |
|---|---|
| Simple | Type `row.pop('in_stock', None)` in the in_stock input, `row.pop('brand', None)` in the brand input |
| JSON Transform | `remove in_stock` on one line, `remove brand` on the next |

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

**Rename a single column (preserving column order):**

| Mode | Code | Order preserved? |
|---|---|---|
| JSON Transform | `rename name to product_name` | Yes |
| Simple (name input) | see below | Depends on approach |

In the **JSON Transform tab**, `rename` preserves column position automatically.

In **Simple/Advanced mode**, `row.pop()` + assign moves the column to the **end**. To preserve order, rebuild the dict:

```python
# BAD — moves product_name to the end:
def apply_rules(row):
    row['product_name'] = row.pop('name', '')
    return row

# GOOD — preserves column position:
def apply_rules(row):
    return {('product_name' if k == 'name' else k): v for k, v in row.items()}
```

**Simple mode shortcut:** If column order doesn't matter, `row['product_name'] = row.pop('name', '')` is fine. If it does, use Advanced mode with the dict comprehension above, or add a reorder step after renaming.

**Rename multiple columns (preserving order):**
```python
def apply_rules(row):
    renames = {
        'name': 'product_name',
        'brand': 'manufacturer',
        'price': 'unit_price',
        'in_stock': 'available',
    }
    return {renames.get(k, k): v for k, v in row.items()}
```

Or in JSON Transform tab (multiple lines):
```
rename name to product_name
rename brand to manufacturer
rename price to unit_price
rename in_stock to available
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

Filtering works by returning `None` from `apply_rules` to skip a row. In Simple mode, type the filter line in any column input or use "+ Add Line". In the JSON Transform tab, use natural-language `filter` rules.

**Filter by exact value:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if row.get('brand') != 'TechBrand': return None` |
| JSON Transform | `filter brand equals TechBrand` |

```python
# Advanced mode (full function):
def apply_rules(row):
    if row.get('brand') != 'TechBrand':
        return None
    return row
# Keeps only TechBrand products (id 1, 4)
```

**Filter by numeric comparison:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if float(row.get('price', 0)) < 100: return None` |
| JSON Transform | `filter price >= 100` |

```python
def apply_rules(row):
    if float(row.get('price', 0)) < 100:
        return None
    return row
# Removes Wireless Earbuds (79.99) and Bluetooth Speaker (59.99)
```

**Filter by boolean field:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not row.get('in_stock'): return None` |

```python
def apply_rules(row):
    if not row.get('in_stock'):
        return None
    return row
# Removes Smart Watch (in_stock: false)
```

**Filter by text contains:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if 'Smart' not in str(row.get('name', '')): return None` |
| JSON Transform | `filter name contains Smart` |

```python
def apply_rules(row):
    if 'Smart' not in str(row.get('name', '')):
        return None
    return row
# Keeps only "Smart Watch"
```

**Filter by text starts with / ends with:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not str(row.get('name', '')).startswith('Bluetooth'): return None` |
| JSON Transform | `filter name startswith Bluetooth` |

```python
def apply_rules(row):
    if not str(row.get('name', '')).startswith('Bluetooth'):
        return None
    return row
# Keeps only "Bluetooth Speaker"
```

**Filter by multiple conditions (AND):**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not (row.get('brand') == 'TechBrand' and float(row.get('price', 0)) > 500): return None` |

```python
def apply_rules(row):
    if row.get('brand') == 'TechBrand' and float(row.get('price', 0)) > 500:
        return row
    return None
# Keeps only Laptop Pro (TechBrand, 1299.99)
```

**Filter by multiple conditions (OR):**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not (row.get('brand') == 'SoundMax' or float(row.get('price', 0)) > 1000): return None` |

```python
def apply_rules(row):
    if row.get('brand') == 'SoundMax' or float(row.get('price', 0)) > 1000:
        return row
    return None
# Keeps SoundMax products + Laptop Pro
```

**Filter by value in a list:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if row.get('brand') not in ['TechBrand', 'WristTech']: return None` |

```python
def apply_rules(row):
    allowed = ['TechBrand', 'WristTech']
    if row.get('brand') not in allowed:
        return None
    return row
# Keeps TechBrand and WristTech products
```

**Filter by price range:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not (50 <= float(row.get('price', 0)) <= 300): return None` |

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

With `reorder`, you list only the columns you want first — **unlisted columns stay in their original order** automatically. This means you can reorder just one or two columns without listing everything.

Given original columns: `id, name, brand, price, in_stock`

| What you want | JSON Transform rule | Result order |
|---|---|---|
| Move `price` first | `reorder price` | price, id, name, brand, in_stock |
| Move `price, id` first | `reorder price, id` | price, id, name, brand, in_stock |
| Move `in_stock` first | `reorder in_stock` | in_stock, id, name, brand, price |
| Full custom order | `reorder brand, name, id, price` | brand, name, id, price, in_stock |

**JSON Transform tab:**

Move specific columns to the front (rest stay in original order):
```
reorder price, id
```

Full reorder:
```
reorder id, brand, name, price, in_stock
```

Combine rename + reorder:
```
rename name to product_name
rename brand to manufacturer
reorder id, product_name, manufacturer, price
```

**Simple mode ("+ Add Line"):**

Move one column to the front:
```python
return {'price': row.get('price'), **{k: v for k, v in row.items() if k != 'price'}}
```

Move multiple columns to the front:
```python
return {'price': row.get('price'), 'id': row.get('id'), **{k: v for k, v in row.items() if k not in ('price', 'id')}}
```

Full reorder:
```python
return {k: row[k] for k in ['id', 'name', 'price', 'brand'] if k in row}
```

**Advanced mode:**

Move specific columns to the front (rest stay in original order):
```python
def apply_rules(row):
    front = ['price', 'id']
    rest = {k: v for k, v in row.items() if k not in front}
    return {k: row.get(k) for k in front} | rest
```

Full reorder:
```python
def apply_rules(row):
    order = ['id', 'brand', 'name', 'price', 'in_stock']
    return {k: row[k] for k in order if k in row}
```

Rename + reorder together:
```python
def apply_rules(row):
    renames = {'name': 'product_name', 'brand': 'manufacturer'}
    row = {renames.get(k, k): v for k, v in row.items()}
    order = ['id', 'product_name', 'manufacturer', 'price']
    return {k: row[k] for k in order if k in row}
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

All filter examples below work in Simple mode (type the one-liner in "+ Add Line"), Advanced mode (inside `def apply_rules`), or JSON Transform tab (natural-language rules where noted).

**Filter by exact value:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if row['category'] != 'Electronics': return None` |
| JSON Transform | `filter category equals Electronics` |

```python
def apply_rules(row):
    if row['category'] != 'Electronics':
        return None
    return row
# Keeps: Wireless Mouse, USB-C Hub, Mechanical Keyboard
```

**Filter by numeric comparison:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if float(row['price']) < 50: return None` |
| JSON Transform | `filter price >= 50` |

```python
def apply_rules(row):
    if float(row['price']) < 50:
        return None
    return row
# Removes: Wireless Mouse (29.99), USB-C Hub (49.99)
```

**Filter by stock level:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if int(row['stock_qty']) < 50: return None` |
| JSON Transform | `filter stock_qty >= 50` |

```python
def apply_rules(row):
    if int(row['stock_qty']) < 50:
        return None
    return row
# Removes: Standing Desk (12), Monitor Arm (45)
```

**Filter by text contains:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if 'Mouse' not in row['product_name'] and 'Keyboard' not in row['product_name']: return None` |
| JSON Transform | `filter product_name contains Mouse` |

```python
def apply_rules(row):
    if 'Mouse' not in row['product_name'] and 'Keyboard' not in row['product_name']:
        return None
    return row
# Keeps: Wireless Mouse, Mechanical Keyboard
```

**Filter by text starts with / ends with:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not row['product_name'].startswith('Wireless'): return None` |
| JSON Transform | `filter product_name startswith Wireless` |

```python
def apply_rules(row):
    if not row['product_name'].startswith('Wireless'):
        return None
    return row
# Keeps only "Wireless Mouse"
```

| Mode | Code |
|---|---|
| Simple / Advanced | `if not row['product_name'].endswith('Desk'): return None` |
| JSON Transform | `filter product_name endswith Desk` |

```python
def apply_rules(row):
    if not row['product_name'].endswith('Desk'):
        return None
    return row
# Keeps only "Standing Desk"
```

**Filter by multiple conditions (AND):**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not (row['category'] == 'Electronics' and float(row['price']) > 50): return None` |

```python
def apply_rules(row):
    if row['category'] == 'Electronics' and float(row['price']) > 50:
        return row
    return None
# Keeps: Mechanical Keyboard (Electronics, 89.99)
```

**Filter by multiple conditions (OR):**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not (row['supplier'] == 'TechCorp' or float(row['price']) >= 100): return None` |

```python
def apply_rules(row):
    if row['supplier'] == 'TechCorp' or float(row['price']) >= 100:
        return row
    return None
# Keeps: Wireless Mouse, USB-C Hub (TechCorp), Standing Desk, Monitor Arm (>= 100)
```

**Filter by value in a list:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if row['supplier'] not in ['TechCorp', 'KeyMaster']: return None` |

```python
def apply_rules(row):
    allowed_suppliers = ['TechCorp', 'KeyMaster']
    if row['supplier'] not in allowed_suppliers:
        return None
    return row
# Keeps: TechCorp and KeyMaster products
```

**Filter by price range:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if not (30 <= float(row['price']) <= 100): return None` |

```python
def apply_rules(row):
    price = float(row['price'])
    if 30 <= price <= 100:
        return row
    return None
# Keeps: USB-C Hub (49.99), Mechanical Keyboard (89.99)
```

**Filter by SKU pattern:**

| Mode | Code |
|---|---|
| Simple / Advanced | `if int(row['sku'].split('-')[1]) > 3: return None` |

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

Given original columns: `sku, product_name, category, price, stock_qty, supplier`

| What you want | JSON Transform rule | Result order |
|---|---|---|
| Move `price` first | `reorder price` | price, sku, product_name, category, stock_qty, supplier |
| Move `price, sku` first | `reorder price, sku` | price, sku, product_name, category, stock_qty, supplier |
| Full custom order | `reorder sku, product_name, category, supplier, price, stock_qty` | as listed |

**JSON Transform tab:**

Move specific columns to the front:
```
reorder price, sku
```

Rename + reorder:
```
rename product_name to name
rename stock_qty to quantity
reorder sku, name, category, price, quantity, supplier
```

**Simple mode ("+ Add Line"):**

Move one column to the front:
```python
return {'price': row.get('price'), **{k: v for k, v in row.items() if k != 'price'}}
```

Full reorder:
```python
return {k: row[k] for k in ['sku', 'product_name', 'category', 'supplier', 'price', 'stock_qty'] if k in row}
```

**Advanced mode:**

Move specific columns to the front:
```python
def apply_rules(row):
    front = ['price', 'sku']
    rest = {k: v for k, v in row.items() if k not in front}
    return {k: row.get(k) for k in front} | rest
```

Rename + reorder together:
```python
def apply_rules(row):
    renames = {'product_name': 'name', 'stock_qty': 'quantity'}
    row = {renames.get(k, k): v for k, v in row.items()}
    order = ['sku', 'name', 'category', 'price', 'quantity', 'supplier']
    return {k: row[k] for k in order if k in row}
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
│   ├── executor.py                 # Sandboxed code execution + natural-language rule engine
│   ├── views_file.py               # File upload, job mgmt, and JSON transform views
│   ├── urls.py
│   └── maps/
│       ├── json_to_csv_file.py     # JSON-to-CSV mapper
│       └── csv_to_json_file.py     # CSV-to-JSON mapper
├── templates/
│   └── index.html                  # Single-page UI (Convert, JSON Transform, History tabs)
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

### JSON Transform

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mapping/transform/upload/` | Upload JSON file, get table preview |
| `POST` | `/api/mapping/transform/apply/` | Apply natural-language rules, get transformed preview |

#### Upload JSON

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | JSON file (`.json`) |

**Response:**
```json
{
  "status": "ok",
  "preview": {
    "columns": ["name", "age", "salary"],
    "rows": [{"name": "Alice", "age": "25", "salary": "50000"}, ...],
    "total_rows": 100,
    "total_columns": 3,
    "preview_rows": 100
  },
  "data": [...]
}
```

#### Apply Rules

**Request:** `application/json`

```json
{
  "data": [{"name": "alice", "age": 25}, ...],
  "rules": "uppercase name\nfilter age > 18\nsort by age desc"
}
```

**Supported rules:**

| Category | Rule Syntax | Example |
|----------|-------------|---------|
| Text | `uppercase <col>` | `uppercase name` |
| Text | `lowercase <col>` | `lowercase email` |
| Text | `titlecase <col>` | `titlecase city` |
| Text | `trim <col>` | `trim name` |
| Text | `replace in <col> <old> with <new>` | `replace in name Pro with Professional` |
| Text | `regex replace <pat> with <rep> in <col>` | `regex replace \d+ with # in phone` |
| Text | `concat <col1> <col2> as <new>` | `concat first last as full_name` |
| Filter | `filter <col> > <val>` | `filter age > 18` |
| Filter | `filter <col> equals <val>` | `filter status equals active` |
| Filter | `filter <col> != <val>` | `filter brand != Unknown` |
| Filter | `filter <col> contains <text>` | `filter name contains smith` |
| Filter | `filter <col> startswith <text>` | `filter sku startswith PRD` |
| Filter | `filter <col> endswith <text>` | `filter email endswith .com` |
| Sort | `sort by <col> asc` | `sort by name asc` |
| Sort | `sort by <col> desc` | `sort by salary desc` |
| Sort | `sort by <c1> asc, <c2> desc` | `sort by dept asc, salary desc` |
| Column | `rename <old> to <new>` | `rename first_name to name` |
| Column | `remove <col>` | `remove temp_id` |
| Column | `duplicate <col> as <new>` | `duplicate price as original_price` |
| Column | `create <new> = <col1> + <col2>` | `create full_name = first + last` |
| Column | `create <new> = <col> * <num>` | `create bonus = salary * 0.1` |
| Column | `reorder <col1>, <col2>, ...` | `reorder id, name, price` |

**Response:**
```json
{
  "status": "ok",
  "preview": {
    "columns": ["name", "age"],
    "rows": [{"name": "ALICE", "age": "25"}],
    "total_rows": 1,
    "total_columns": 2,
    "preview_rows": 1
  },
  "logs": ["Parsing 3 rule(s)", "Rule 1: Uppercased column \"name\"", ...]
}
```

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
| `GET` | `/` | Web UI — Convert, JSON Transform, and History tabs |

---

## How to Test — Step-by-Step Examples

### Test Data Files

| File | Format | Columns | Rows |
|---|---|---|---|
| `test_data/sample.json` | JSON | id, name, brand, price, in_stock | 5 |
| `test_data/products.csv` | CSV | sku, product_name, category, price, stock_qty, supplier | 5 |
| `test_data/employees.csv` | CSV | emp_id, first_name, last_name, email, department, salary, hire_date, is_active | 10 |
| `test_data/orders_semicolon.csv` | CSV (`;` delimiter) | order_id, customer, product, quantity, unit_price, order_date | 4 |

---

### Test 1: Simple Mode — Variables + Column Rules + Code Block

**File:** `test_data/sample.json` (JSON to CSV)

**Goal:** Add serial number, rename columns, uppercase names, add tax, filter out-of-stock, reorder columns.

**Steps:**

1. Open **http://localhost:8001**, select **JSON to CSV**, upload `test_data/sample.json`
2. Preview shows 5 rows: id, name, brand, price, in_stock

3. **Variables section** — click "+ Add Variable" twice:

   | Name | Value |
   |---|---|
   | `counter` | `{'n': 0}` |
   | `brand_country` | `{'TechBrand': 'USA', 'SoundMax': 'Japan', 'WristTech': 'South Korea'}` |

4. **Column rules** — type in each column's input:

   | Column | Code |
   |---|---|
   | `name` | `row['product_name'] = row.pop('name', '').upper()` |
   | `brand` | `row['manufacturer'] = row.pop('brand', '')` |
   | `in_stock` | `if not row.get('in_stock'): return None` |

5. **Additional Rules** — click "+ Add Line" three times:

   | Code |
   |---|
   | `counter['n'] += 1` |
   | `row['serial'] = counter['n']` |
   | `row['country'] = brand_country.get(row.get('manufacturer'), 'Unknown')` |

6. **Code Block** — type:

   ```python
   row['tax'] = round(float(row['price']) * 0.08, 2)
   row['total'] = round(float(row['price']) * 1.08, 2)
   row.pop('in_stock', None)

   order = ['serial', 'id', 'product_name', 'manufacturer', 'country', 'price', 'tax', 'total']
   row = {k: row[k] for k in order if k in row}
   ```

7. Click **Convert to CSV**

**Expected result:** 4 rows (Smart Watch filtered out), 8 columns:

| serial | id | product_name | manufacturer | country | price | tax | total |
|---|---|---|---|---|---|---|---|
| 1 | 1 | LAPTOP PRO | TechBrand | USA | 1299.99 | 104.0 | 1403.99 |
| 2 | 2 | WIRELESS EARBUDS | SoundMax | Japan | 79.99 | 6.4 | 86.39 |
| 3 | 4 | TABLET MINI | TechBrand | USA | 449.99 | 36.0 | 485.99 |
| 4 | 5 | BLUETOOTH SPEAKER | SoundMax | Japan | 59.99 | 4.8 | 64.79 |

8. Click **Advanced** mode — verify the generated code matches:

```python
counter = {'n': 0}
brand_country = {'TechBrand': 'USA', 'SoundMax': 'Japan', 'WristTech': 'South Korea'}

def apply_rules(row):
    row['product_name'] = row.pop('name', '').upper()
    row['manufacturer'] = row.pop('brand', '')
    if not row.get('in_stock'): return None
    counter['n'] += 1
    row['serial'] = counter['n']
    row['country'] = brand_country.get(row.get('manufacturer'), 'Unknown')

    row['tax'] = round(float(row['price']) * 0.08, 2)
    row['total'] = round(float(row['price']) * 1.08, 2)
    row.pop('in_stock', None)

    order = ['serial', 'id', 'product_name', 'manufacturer', 'country', 'price', 'tax', 'total']
    row = {k: row[k] for k in order if k in row}
    return row
```

---

### Test 2: Simple Mode — For Loops in Code Block

**File:** `test_data/products.csv` (CSV to JSON)

**Goal:** Uppercase multiple columns, set defaults, add computed columns using loops.

**Steps:**

1. Select **CSV to JSON**, upload `test_data/products.csv`

2. **Code Block** — type:

   ```python
   for col in ['product_name', 'category', 'supplier']:
       row[col] = str(row[col]).strip().upper()

   row['price'] = float(row['price'])
   row['stock_qty'] = int(row['stock_qty'])
   row['inventory_value'] = round(row['price'] * row['stock_qty'], 2)

   if row['price'] > 100:
       row['tier'] = 'Premium'
   elif row['price'] > 50:
       row['tier'] = 'Mid-Range'
   else:
       row['tier'] = 'Budget'
   ```

3. Click **Convert to JSON**

**Expected result:** 5 rows with uppercase text, typed numbers, and new columns:

```json
{
  "sku": "SKU-001",
  "product_name": "WIRELESS MOUSE",
  "category": "ELECTRONICS",
  "price": 29.99,
  "stock_qty": 150,
  "supplier": "TECHCORP",
  "inventory_value": 4498.5,
  "tier": "Budget"
}
```

---

### Test 3: Simple Mode — Datetime (No Import Needed)

**File:** `test_data/sample.json` (JSON to CSV)

**Goal:** Add current date/time columns — `datetime`, `timedelta`, `math`, `uuid` etc. are all auto-available without any import.

**Steps:**

1. Select **JSON to CSV**, upload `test_data/sample.json`
2. Stay in **Simple** mode — click **"+ Add Line"** three times:

   | Code |
   |---|
   | `row['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')` |
   | `row['date_only'] = datetime.now().strftime('%d/%m/%Y')` |
   | `row['tomorrow'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')` |

3. Click **Convert to CSV**

**Expected result:** 5 rows, 8 columns (original 5 + created_at, date_only, tomorrow)

> No import statement needed — `datetime`, `timedelta`, `math`, `json`, `uuid`, `hashlib`, `re`, `random`, `base64`, etc. are all pre-loaded automatically.

---

### Test 4: JSON Transform Tab — Natural-Language Rules

**File:** `test_data/sample.json`

**Goal:** Uppercase names, filter by price, sort, rename, add computed column, reorder.

**Steps:**

1. Click the **JSON Transform** tab
2. Upload `test_data/sample.json`
3. Original data grid shows 5 rows: id, name, brand, price, in_stock

4. Type these rules in the rule editor:

   ```
   uppercase name
   filter price > 100
   sort by price desc
   rename name to product_name
   rename brand to manufacturer
   create tax = price * 0.08
   reorder id, product_name, manufacturer, price, tax
   ```

5. Click **Apply Rules** (or press Ctrl+Enter)

**Expected result:**

Before (5 rows) → After (3 rows, price > 100):

| id | product_name | manufacturer | price | tax |
|---|---|---|---|---|
| 1 | LAPTOP PRO | TechBrand | 1299.99 | 104.0 |
| 4 | TABLET MINI | TechBrand | 449.99 | 36.0 |
| 3 | SMART WATCH | WristTech | 249.99 | 20.0 |

Execution log should show:
```
Parsing 7 rule(s)
Rule 1: Uppercased column "name"
Rule 2: Filtered "price" > "100" - 5 -> 3 rows
Rule 3: Sorted by price desc
Rule 4: Renamed "name" -> "product_name"
Rule 5: Renamed "brand" -> "manufacturer"
Rule 6: Created "tax" = price * 0.08
Rule 7: Reordered columns to ['id', 'product_name', 'manufacturer', 'price', 'tax']
Done: 3 rows in output
```

---

### Test 5: JSON Transform Tab — Filter Examples

**File:** `test_data/sample.json`

**Test each filter type one at a time:**

| Rule | Expected rows kept |
|---|---|
| `filter price > 100` | 3 rows (Laptop Pro, Smart Watch, Tablet Mini) |
| `filter price >= 249.99` | 3 rows (Laptop Pro, Smart Watch, Tablet Mini) |
| `filter price < 100` | 2 rows (Wireless Earbuds, Bluetooth Speaker) |
| `filter brand equals TechBrand` | 2 rows (Laptop Pro, Tablet Mini) |
| `filter brand != SoundMax` | 3 rows (Laptop Pro, Smart Watch, Tablet Mini) |
| `filter name contains Smart` | 1 row (Smart Watch) |
| `filter name startswith Laptop` | 1 row (Laptop Pro) |
| `filter name endswith Speaker` | 1 row (Bluetooth Speaker) |
| `filter in_stock equals true` | 4 rows (all except Smart Watch) |

---

### Test 6: JSON Transform Tab — Reorder

**File:** `test_data/sample.json`

**Test partial reorder:**

```
reorder price, name
```

**Expected:** Columns in order: `price, name, id, brand, in_stock` (price and name first, rest in original order)

**Test rename + reorder:**

```
rename name to product_name
rename brand to manufacturer
reorder id, product_name, manufacturer, price
```

**Expected:** Columns in order: `id, product_name, manufacturer, price, in_stock`

---

### Test 7: CSV with Semicolon Delimiter

**File:** `test_data/orders_semicolon.csv` (CSV to JSON)

**Steps:**

1. Select **CSV to JSON**
2. Upload `test_data/orders_semicolon.csv`
3. Set **Delimiter** to `;`
4. Switch to **Advanced** mode, type:

   ```python
   def apply_rules(row):
       row['quantity'] = int(row['quantity'])
       row['unit_price'] = float(row['unit_price'])
       row['total'] = round(row['quantity'] * row['unit_price'], 2)
       return row
   ```

5. Click **Convert to JSON**

**Expected result:** 4 rows with typed numbers and new `total` column:

| order_id | customer | product | quantity | unit_price | total |
|---|---|---|---|---|---|
| ORD-2001 | Acme Corp | Widget A | 50 | 12.50 | 625.0 |
| ORD-2002 | Globex Inc | Gadget B | 25 | 34.00 | 850.0 |
| ORD-2003 | Acme Corp | Widget C | 100 | 8.75 | 875.0 |
| ORD-2004 | Initech | Gadget B | 10 | 34.00 | 340.0 |

---

### Test 8: Employees CSV — For Loop + Variables

**File:** `test_data/employees.csv` (CSV to JSON)

**Steps:**

1. Select **CSV to JSON**, upload `test_data/employees.csv`
2. Switch to **Advanced** mode, type:

   ```python
   from datetime import datetime

   dept_budgets = {
       'Engineering': 500000,
       'Marketing': 200000,
       'HR': 150000,
       'Finance': 300000,
   }

   counter = {'n': 0}

   def apply_rules(row):
       if row['is_active'] != 'true':
           return None

       counter['n'] += 1
       salary = float(row['salary'])
       dept = row['department']

       row['serial'] = counter['n']
       row['salary'] = salary
       row['full_name'] = row['first_name'] + ' ' + row['last_name']
       row['email_domain'] = row['email'].split('@')[1]
       row['dept_budget'] = dept_budgets.get(dept, 0)
       row['salary_pct'] = str(round(salary / dept_budgets.get(dept, 1) * 100, 1)) + '%'
       row['years'] = datetime.now().year - int(row['hire_date'][:4])

       for col in ['first_name', 'last_name', 'is_active']:
           row.pop(col, None)

       order = ['serial', 'emp_id', 'full_name', 'email', 'department',
                'salary', 'dept_budget', 'salary_pct', 'hire_date', 'years']
       return {k: row.get(k) for k in order}
   ```

3. Click **Convert to JSON**

**Expected result:** 8 rows (Eve and Jack filtered out — `is_active: false`), with computed columns:

| serial | emp_id | full_name | department | salary | salary_pct | years |
|---|---|---|---|---|---|---|
| 1 | 1001 | Alice Johnson | Engineering | 95000 | 19.0% | 4 |
| 2 | 1002 | Bob Smith | Marketing | 72000 | 36.0% | 5 |
| ... | ... | ... | ... | ... | ... | ... |

---

### Test 9: curl API Tests

All commands use `localhost:8001` (Docker port).

**JSON to CSV — Simple passthrough:**
```bash
curl -X POST http://localhost:8001/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json"
```

**JSON to CSV — With rules:**
```bash
curl -X POST http://localhost:8001/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json" \
  -F "function_name=uppercase_test" \
  -F "rules_code=def apply_rules(row):
    row['name'] = row['name'].upper()
    return row"
```

**CSV to JSON — With type casting:**
```bash
curl -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/products.csv" \
  -F "rules_code=def apply_rules(row):
    row['price'] = float(row['price'])
    row['stock_qty'] = int(row['stock_qty'])
    return row"
```

**CSV with semicolon delimiter:**
```bash
curl -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/orders_semicolon.csv" \
  -F "delimiter=;"
```

**JSON Transform — Upload:**
```bash
curl -X POST http://localhost:8001/api/mapping/transform/upload/ \
  -F "file=@test_data/sample.json"
```

**JSON Transform — Apply rules:**
```bash
curl -X POST http://localhost:8001/api/mapping/transform/apply/ \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      {"id": 1, "name": "Laptop Pro", "brand": "TechBrand", "price": 1299.99},
      {"id": 2, "name": "Earbuds", "brand": "SoundMax", "price": 79.99}
    ],
    "rules": "uppercase name\nfilter price > 100\nsort by price desc"
  }'
```

**List jobs:**
```bash
curl http://localhost:8001/api/mapping/file/jobs/
curl http://localhost:8001/api/mapping/file/jobs/?status=completed
curl http://localhost:8001/api/mapping/file/jobs/?status=failed
```

**Download output file (replace `<job_id>` with UUID from response):**
```bash
curl -OJ http://localhost:8001/api/mapping/file/jobs/<job_id>/download/
```

---

### Test 10: Error Handling

**Wrong function name:**
```python
def wrong_name(row):
    return row
```
Expected: `Your code must define a function named "apply_rules"`

**Blocked import (os):**
```python
import os
def apply_rules(row):
    return row
```
Expected: `Security error: import of "os" is not allowed`

**Unknown import:**
```python
import requests
def apply_rules(row):
    return row
```
Expected: `Import of "requests" is not allowed. Allowed modules: base64, collections, datetime, ...`

**Allowed import works:**
```python
from datetime import datetime
def apply_rules(row):
    row['ts'] = datetime.now().isoformat()
    return row
```
Expected: Success — new `ts` column with ISO timestamp

**Blocked builtin:**
```python
def apply_rules(row):
    open('/etc/passwd')
    return row
```
Expected: `Security error: open() is not allowed`

**Syntax error:**
```python
def apply_rules(row):
    row['name'] = row['name'.upper()
    return row
```
Expected: `Syntax error in your code (line ...)`

**Filter all rows:**
```python
def apply_rules(row):
    return None
```
Expected: `No rows remain after transform (all filtered out or errored)`

**Return wrong type:**
```python
def apply_rules(row):
    return "not a dict"
```
Expected: `apply_rules() must return a dict or None, got str`

**JSON Transform — Invalid rule:**
```
unknown_rule name
```
Expected: `Rule 1: Could not understand rule: "unknown_rule name"`

**JSON Transform — Column not found:**
```
uppercase nonexistent_column
```
Expected: `Column "nonexistent_column" not found. Available: id, name, brand, price, in_stock`
