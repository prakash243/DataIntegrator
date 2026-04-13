"""
Example apply_rules() functions for use with the Data Integrator.

Each example below is a standalone function. Copy one into the
Simple mode code editor or Advanced mode editor when converting files.

The examples are organized by input format:
  - JSON / CSV examples (sample.json, products.csv)
  - EDI examples (sample_850.edi, sample_810.edi)
"""

# ============================================================================
# JSON / CSV EXAMPLES
# ============================================================================

# --- Example 1: JSON to CSV — Filter, rename, enrich (sample.json) ---------

counter = {'n': 0}

def apply_rules(row):
    # Filter: skip out-of-stock items
    if not row.get('in_stock'):
        return None

    counter['n'] += 1
    brand_country = {'TechBrand': 'USA', 'SoundMax': 'Japan', 'WristTech': 'South Korea'}
    # Rename columns
    row['product_name'] = row.pop('name', '')
    row['manufacturer'] = row.pop('brand', '')

    # Text transforms
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


# --- Example 2: CSV to JSON — Nested supplier hierarchy (products.csv) -----

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


# --- Example 3: Datetime operations ----------------------------------------

from datetime import datetime, timedelta
import math

def apply_rules(row):
    row['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row['date_only'] = datetime.now().strftime('%d/%m/%Y')
    row['tomorrow'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    row['price_sqrt'] = round(math.sqrt(float(row['price'])), 2)
    return row


# --- Example 4: Counter / sequencing ---------------------------------------

counter = {'n': 0}

def apply_rules(row):
    counter['n'] += 1
    row['serial_no'] = counter['n']
    return row


# --- Example 5: Column rename + reorder ------------------------------------

counter = {'n': 0}

def apply_rules(row):
    counter['n'] += 1
    row['serial_no'] = counter['n']
    renames = {'name': 'product_name', 'brand': 'manufacturer'}
    row = {renames.get(k, k): v for k, v in row.items()}
    order = ['serial_no', 'id', 'product_name', 'manufacturer', 'price']
    return {k: row[k] for k in order if k in row}


# ============================================================================
# EDI (X12) EXAMPLES
# ============================================================================

# --- Example 6: EDI 850 to JSON — Clean up purchase order line items -------
# Use with: sample_850.edi (EDI to JSON direction)
# The EDI parser produces rows with fields like: line_number, quantity_ordered,
# unit_price, product_id, purchase_order_number, BY_name, etc.

def apply_rules(row):
    # Calculate line total
    qty = float(row.get('quantity_ordered', 0))
    price = float(row.get('unit_price', 0))
    row['line_total'] = round(qty * price, 2)

    # Format the order date (YYYYMMDD → YYYY-MM-DD)
    date_raw = row.get('order_date', '')
    if len(date_raw) == 8:
        row['order_date'] = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"

    # Clean up product ID
    row['product_id'] = str(row.get('product_id', '')).strip()

    # Keep only the most useful columns
    order = [
        'purchase_order_number', 'order_date', 'BY_name',
        'line_number', 'product_id', 'quantity_ordered',
        'unit_of_measure', 'unit_price', 'line_total',
    ]
    return {k: row.get(k, '') for k in order}


# --- Example 7: EDI 850 to CSV — Filter high-value line items -------------
# Use with: sample_850.edi (EDI to CSV direction)

def apply_rules(row):
    # Only keep line items with total value >= $1000
    qty = float(row.get('quantity_ordered', 0))
    price = float(row.get('unit_price', 0))
    total = qty * price
    if total < 1000:
        return None

    row['line_total'] = round(total, 2)
    row['product_id'] = str(row.get('product_id', '')).strip()
    row['quantity_ordered'] = int(qty)
    row['unit_price'] = round(price, 2)

    # Remove envelope and metadata fields
    for key in list(row.keys()):
        if key.startswith('edi_') or key.startswith('SE_') or key.startswith('ST_'):
            row.pop(key, None)

    return row


# --- Example 8: EDI 810 to JSON — Invoice summary -------------------------
# Use with: sample_810.edi (EDI to JSON direction)
# The 810 parser produces rows with: line_number, quantity_invoiced,
# unit_price, product_id, invoice_date, invoice_number, etc.

counter = {'n': 0}

def apply_rules(row):
    counter['n'] += 1

    qty = float(row.get('quantity_invoiced', 0))
    price = float(row.get('unit_price', 0))

    # Format invoice date
    inv_date = row.get('invoice_date', '')
    if len(inv_date) == 8:
        inv_date = f"{inv_date[:4]}-{inv_date[4:6]}-{inv_date[6:]}"

    return {
        'item_no': counter['n'],
        'invoice_number': row.get('invoice_number', ''),
        'invoice_date': inv_date,
        'po_number': row.get('purchase_order_number', ''),
        'product_id': str(row.get('product_id', '')).strip(),
        'quantity': int(qty),
        'unit_price': round(price, 2),
        'line_total': round(qty * price, 2),
        'currency': 'USD',
    }


# --- Example 9: EDI to JSON — Strip envelope fields, rename segments ------
# Use with: any EDI file (EDI to JSON direction)
# Generic transform that works with any transaction set

def apply_rules(row):
    # Remove all envelope/metadata fields
    for key in list(row.keys()):
        if key.startswith('edi_'):
            row.pop(key, None)

    # Clean up: strip whitespace from all string values
    for key in row:
        if isinstance(row[key], str):
            row[key] = row[key].strip()

    # Remove empty values
    row = {k: v for k, v in row.items() if v}

    return row


# --- Example 10: EDI 850 to CSV — Full order enrichment -------------------
# Use with: sample_850.edi (EDI to CSV direction)
# Adds computed columns, reformats dates, assigns priority

counter = {'n': 0}
priority_thresholds = {'high': 5000, 'medium': 1000}

def apply_rules(row):
    counter['n'] += 1

    qty = float(row.get('quantity_ordered', 0))
    price = float(row.get('unit_price', 0))
    line_total = round(qty * price, 2)

    # Assign priority based on line total
    if line_total >= priority_thresholds['high']:
        priority = 'HIGH'
    elif line_total >= priority_thresholds['medium']:
        priority = 'MEDIUM'
    else:
        priority = 'LOW'

    # Format date
    date_raw = row.get('order_date', '')
    formatted_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}" if len(date_raw) == 8 else date_raw

    order = [
        'row_num', 'po_number', 'order_date', 'buyer',
        'line_number', 'product_id', 'quantity', 'unit_price',
        'line_total', 'priority',
    ]
    return {k: v for k, v in {
        'row_num': counter['n'],
        'po_number': row.get('purchase_order_number', ''),
        'order_date': formatted_date,
        'buyer': row.get('BY_name', ''),
        'line_number': row.get('line_number', ''),
        'product_id': str(row.get('product_id', '')).strip(),
        'quantity': int(qty),
        'unit_price': round(price, 2),
        'line_total': line_total,
        'priority': priority,
    }.items() if k in order}
