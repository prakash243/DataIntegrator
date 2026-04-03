# Data Integrator — JSON & CSV Converter

A Django REST Framework application that converts between **JSON and CSV** formats using **user-defined Python rule functions**. Users upload a file, write a `def apply_rules(row):` function to modify each row, and get the converted output with a live preview.

**Supported conversions:**
- **JSON to CSV** — Upload a JSON file (array of objects), get a CSV file
- **CSV to JSON** — Upload a CSV file, get a JSON file (array of objects)

---

## Setup, Run & Test (Docker)

### Prerequisites

- Docker and Docker Compose installed ([Install Docker](https://docs.docker.com/get-docker/))

### Step 1: Clone the Repository

```bash
git clone <repo-url>
cd DataIntegrator
```

### Step 2: Build and Start the Container

```bash
docker compose up -d --build
```

This builds the image (Python 3.12, installs Django + DRF) and starts the container in the background.

Verify the container is running:

```bash
docker compose ps
```

You should see the `web` service with status `Up` on port `8001`.

### Step 3: Run Database Migrations

```bash
docker compose exec web python manage.py migrate
```

This creates the SQLite database and all required tables (`ConversionJob`, etc.).

### Step 4: Open the App

Open **http://localhost:8001** in your browser.

You should see the Data Integrator UI with:
- A direction toggle (JSON to CSV / CSV to JSON)
- An upload zone
- The History tab

---

### Step 5: Test JSON to CSV

**Test data:** `test_data/sample.json`
```json
[
  {"id": 1, "name": "Laptop Pro", "brand": "TechBrand", "price": 1299.99, "in_stock": true},
  {"id": 2, "name": "Wireless Earbuds", "brand": "SoundMax", "price": 79.99, "in_stock": true},
  {"id": 3, "name": "Smart Watch", "brand": "WristTech", "price": 249.99, "in_stock": false},
  {"id": 4, "name": "Tablet Mini", "brand": "TechBrand", "price": 449.99, "in_stock": true},
  {"id": 5, "name": "Bluetooth Speaker", "brand": "SoundMax", "price": 59.99, "in_stock": true}
]
```

#### 5a. Simple passthrough (no rules)

1. Make sure **JSON to CSV** is selected (default)
2. Click the upload zone and select `test_data/sample.json`
3. You should see a **preview table** with 5 rows and 5 columns
4. Leave the code editor as-is (default `def apply_rules(row): return row`)
5. Click **Convert to CSV**
6. **Expected result:** Green "Completed" badge, 5 rows, 5 columns
7. Click **Download CSV** — open the file and verify all 5 rows are present

#### 5b. Uppercase names + add discount column

1. Upload `test_data/sample.json` again
2. Replace the code editor with:
   ```python
   def apply_rules(row):
       row['name'] = row['name'].upper()
       row['discounted'] = round(float(row['price']) * 0.9, 2)
       return row
   ```
3. Click **Convert to CSV**
4. **Expected result:** 5 rows, 6 columns (new `discounted` column added)
5. CSV preview should show: `LAPTOP PRO`, `WIRELESS EARBUDS`, etc. with discount prices

#### 5c. Filter rows + rename + remove column

1. Upload `test_data/sample.json` again
2. Replace the code editor with:
   ```python
   def apply_rules(row):
       # Filter: skip out-of-stock items
       if not row.get('in_stock'):
           return None

       # Rename columns
       row['product_name'] = row.pop('name', '')
       row['manufacturer'] = row.pop('brand', '')

       # Add new column
       row['tier'] = 'Premium' if float(row['price']) >= 500 else 'Standard'

       # Remove column
       row.pop('in_stock', None)

       return row
   ```
3. Click **Convert to CSV**
4. **Expected result:**
   - 4 rows (Smart Watch filtered out — `in_stock: false`)
   - Columns: `id`, `product_name`, `manufacturer`, `price`, `tier`
   - `in_stock` column removed
   - `name` renamed to `product_name`, `brand` renamed to `manufacturer`

#### 5d. Full combined rules with top-level variables

1. Upload `test_data/sample.json` again
2. Replace the code editor with:
   ```python
   counter = {'n': 0}
   brand_country = {'TechBrand': 'USA', 'SoundMax': 'Japan', 'WristTech': 'South Korea'}

   def apply_rules(row):
       if not row.get('in_stock'):
           return None

       counter['n'] += 1
       price = float(row['price'])

       row['row_num'] = counter['n']
       row['product_name'] = row.pop('name', '').upper()
       row['manufacturer'] = row.pop('brand', '')
       row['country'] = brand_country.get(row['manufacturer'], 'Unknown')
       row['tax'] = round(price * 0.08, 2)
       row['total'] = round(price * 1.08, 2)
       row['tier'] = 'Premium' if price >= 500 else 'Standard'
       row['sku'] = row['manufacturer'][:3].upper() + '-' + str(row['id']).zfill(4)
       row.pop('in_stock', None)

       order = ['row_num', 'sku', 'product_name', 'manufacturer', 'country',
                'price', 'tax', 'total', 'tier']
       return {k: row.get(k) for k in order}
   ```
3. Click **Convert to CSV**
4. **Expected result:** 4 rows, 9 columns:

   | row_num | sku | product_name | manufacturer | country | price | tax | total | tier |
   |---|---|---|---|---|---|---|---|---|
   | 1 | TEC-0001 | LAPTOP PRO | TechBrand | USA | 1299.99 | 104.0 | 1403.99 | Premium |
   | 2 | SOU-0002 | WIRELESS EARBUDS | SoundMax | Japan | 79.99 | 6.4 | 86.39 | Standard |
   | 3 | TEC-0004 | TABLET MINI | TechBrand | USA | 449.99 | 36.0 | 485.99 | Standard |
   | 4 | SOU-0005 | BLUETOOTH SPEAKER | SoundMax | Japan | 59.99 | 4.8 | 64.79 | Standard |

---

### Step 6: Test CSV to JSON

**Test data:** `test_data/products.csv`
```csv
sku,product_name,category,price,stock_qty,supplier
SKU-001,Wireless Mouse,Electronics,29.99,150,TechCorp
SKU-002,USB-C Hub,Electronics,49.99,85,TechCorp
SKU-003,Standing Desk,Furniture,399.00,12,OfficePro
SKU-004,Mechanical Keyboard,Electronics,89.99,200,KeyMaster
SKU-005,Monitor Arm,Furniture,129.99,45,OfficePro
```

#### 6a. Simple passthrough (no rules)

1. Click **CSV to JSON** toggle at the top
2. Upload `test_data/products.csv`
3. You should see a **preview table** with 5 rows and 6 columns
4. Leave the code editor as-is
5. Click **Convert to JSON**
6. **Expected result:** 5 rows — all values are strings (`"29.99"`, `"150"`) because CSV has no type info

#### 6b. Cast types to proper JSON values

1. Upload `test_data/products.csv` again
2. Replace the code editor with:
   ```python
   def apply_rules(row):
       row['price'] = float(row['price'])
       row['stock_qty'] = int(row['stock_qty'])
       return row
   ```
3. Click **Convert to JSON**
4. **Expected result:** 5 rows — `price` is now a number (`29.99` not `"29.99"`), `stock_qty` is an integer

#### 6c. Filter + uppercase + add columns

1. Upload `test_data/products.csv` again
2. Replace the code editor with:
   ```python
   def apply_rules(row):
       # Filter: skip low-stock items
       if int(row['stock_qty']) < 20:
           return None

       # Cast types
       row['price'] = float(row['price'])
       row['stock_qty'] = int(row['stock_qty'])

       # Text transform
       row['product_name'] = row['product_name'].upper()

       # Add computed columns
       row['inventory_value'] = round(row['price'] * row['stock_qty'], 2)
       row['tier'] = 'Premium' if row['price'] >= 200 else 'Standard'

       return row
   ```
3. Click **Convert to JSON**
4. **Expected result:**
   - 4 rows (Standing Desk filtered out — `stock_qty: 12`)
   - Uppercase names: `WIRELESS MOUSE`, `USB-C HUB`, etc.
   - New columns: `inventory_value`, `tier`

#### 6d. Build nested JSON structure

1. Upload `test_data/products.csv` again
2. Replace the code editor with:
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
               'in_stock': int(row['stock_qty']) > 0,
           },
       }
   ```
3. Click **Convert to JSON**
4. **Expected result:** 5 rows with nested objects:
   ```json
   {
     "sku": "SKU-001",
     "product": {"name": "Wireless Mouse", "category": "Electronics"},
     "pricing": {"amount": 29.99, "currency": "USD"},
     "inventory": {"quantity": 150, "supplier": "TechCorp", "in_stock": true}
   }
   ```

#### 6e. Full combined rules with top-level variables

1. Upload `test_data/products.csv` again
2. Replace the code editor with:
   ```python
   counter = {'n': 0}
   supplier_info = {
       'TechCorp': {'country': 'USA', 'discount': 0.15},
       'OfficePro': {'country': 'Germany', 'discount': 0.10},
       'KeyMaster': {'country': 'Japan', 'discount': 0.05},
   }

   def apply_rules(row):
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
3. Click **Convert to JSON**
4. **Expected result:** 4 rows (Standing Desk filtered out):
   ```json
   [
     {
       "index": 1, "product_code": "ELE-001",
       "product": {"name": "WIRELESS MOUSE", "category": "Electronics"},
       "supplier": {"name": "TechCorp", "country": "USA"},
       "pricing": {"original": 29.99, "discounted": 25.49, "discount_pct": "15%", "currency": "USD"},
       "inventory": {"quantity": 150, "value": 4498.5}
     },
     ...
   ]
   ```

---

### Step 7: Test with curl (API)

All curl commands use `localhost:8001` (Docker port).

**JSON to CSV — with rules:**
```bash
curl -X POST http://localhost:8001/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json" \
  -F "function_name=uppercase_test" \
  -F "rules_code=def apply_rules(row):
    row['name'] = row['name'].upper()
    return row"
```

**CSV to JSON — with rules:**
```bash
curl -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/products.csv" \
  -F "function_name=type_cast_test" \
  -F "rules_code=def apply_rules(row):
    row['price'] = float(row['price'])
    row['stock_qty'] = int(row['stock_qty'])
    return row"
```

**Without any rules (passthrough):**
```bash
curl -X POST http://localhost:8001/api/mapping/file/json-to-csv/ \
  -F "file=@test_data/sample.json"
```

**CSV with semicolon delimiter:**
```bash
curl -X POST http://localhost:8001/api/mapping/file/csv-to-json/ \
  -F "file=@test_data/orders_semicolon.csv" \
  -F "delimiter=;"
```

**List all jobs:**
```bash
curl http://localhost:8001/api/mapping/file/jobs/
```

**Filter jobs by status:**
```bash
curl http://localhost:8001/api/mapping/file/jobs/?status=completed
curl http://localhost:8001/api/mapping/file/jobs/?status=failed
```

**Get job detail (replace `<job_id>` with a UUID from the response above):**
```bash
curl http://localhost:8001/api/mapping/file/jobs/<job_id>/
```

**Download output file:**
```bash
curl -OJ http://localhost:8001/api/mapping/file/jobs/<job_id>/download/
```

---

### Step 8: Check Job History (Web UI)

1. Click the **History** tab in the web UI
2. You should see all the conversion jobs you ran above
3. Each row shows: input file, direction (JSON->CSV or CSV->JSON), status, row count, date
4. Use the **status filter** dropdown to show only Completed or Failed jobs
5. Click **Refresh** to reload the list
6. Click **Download** on any completed job to re-download the output file

---

### Step 9: Test Error Handling

Try these in the code editor to verify errors are handled gracefully:

**Wrong function name:**
```python
def wrong_name(row):
    return row
```
Expected: Red "Failed" badge with error `Your code must define a function named "apply_rules"`

**Blocked import:**
```python
import os
def apply_rules(row):
    return row
```
Expected: `Security error: import statements are not allowed`

**Blocked builtins:**
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

---

### Step 10: Stop the Container

```bash
docker compose down
```

To restart later:

```bash
docker compose up -d
```

Your data (SQLite database + uploaded files) persists in the project directory.
