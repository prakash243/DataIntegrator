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
#
# The EDI parser produces rows with:
#   - Header fields:      purchase_order_number, order_date, currency_code, ...
#   - Envelope fields:    edi_sender, edi_receiver, edi_transaction_type
#   - Party fields:       BY_name, BY_city, ST_name, ST_city, SE_name, SE_city
#                         (entity-prefixed: BY=Buyer, ST=ShipTo, SE=Seller, RE=Remit)
#   - Line item fields:   line_number, quantity_ordered, unit_price, product_id,
#                         description (from attached PID segment)
#
# One row is produced per line item (PO1/IT1). Header and party fields repeat
# on every row; only line item fields vary.

# --- Example 6: EDI 850 to JSON — Clean PO line items ----------------------
# Use with: sample_850.edi (EDI to JSON direction)

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

    # Keep only the most useful columns — note party fields are now correctly
    # prefixed per entity (BY_, ST_, SE_)
    order = [
        'purchase_order_number', 'order_date',
        'BY_name', 'BY_city', 'BY_state',
        'SE_name', 'SE_city', 'SE_state',
        'line_number', 'product_id', 'description',
        'quantity_ordered', 'unit_of_measure', 'unit_price', 'line_total',
    ]
    return {k: row.get(k, '') for k in order}


# --- Example 7: EDI 850 to CSV — Use loops to bulk-format fields -----------
# Use with: sample_850.edi (EDI to CSV direction)
# Demonstrates for-loops to process many columns at once

def apply_rules(row):
    # Loop 1: Strip whitespace from all string values
    for key in list(row.keys()):
        if isinstance(row[key], str):
            row[key] = row[key].strip()

    # Loop 2: Format all YYYYMMDD date fields in the row
    for key in list(row.keys()):
        if 'date' in key.lower():
            val = str(row[key])
            if len(val) == 8 and val.isdigit():
                row[key] = f"{val[:4]}-{val[4:6]}-{val[6:]}"

    # Loop 3: Cast numeric fields
    numeric_fields = ['quantity_ordered', 'unit_price', 'line_number']
    for field in numeric_fields:
        if field in row and row[field]:
            try:
                row[field] = float(row[field]) if '.' in str(row[field]) else int(row[field])
            except (ValueError, TypeError):
                pass

    # Compute line total using casted values
    row['line_total'] = round(float(row.get('quantity_ordered', 0)) * float(row.get('unit_price', 0)), 2)

    # Loop 4: Remove envelope/metadata fields we don't need
    for key in list(row.keys()):
        if key.startswith('edi_'):
            row.pop(key, None)

    return row


# --- Example 8: EDI 810 to JSON — Invoice summary with counter -------------
# Use with: sample_810.edi (EDI to JSON direction)

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
        'ship_to': row.get('ST_name', ''),
        'remit_to': row.get('RE_name', ''),
        'product_id': str(row.get('product_id', '')).strip(),
        'description': row.get('description', ''),
        'quantity': int(qty),
        'unit_price': round(price, 2),
        'line_total': round(qty * price, 2),
        'currency': row.get('currency_code', 'USD'),
    }


# --- Example 9: EDI — Collapse party fields into nested dicts --------------
# Use with: any EDI file (EDI to JSON direction)
# Uses loops to group BY_*, ST_*, SE_* fields back into nested party objects

def apply_rules(row):
    # Collect party fields by entity prefix using a loop
    parties = {}
    keys_to_remove = []
    party_prefixes = ('BY_', 'ST_', 'SE_', 'RE_', 'VN_', 'SF_')

    for key in list(row.keys()):
        for prefix in party_prefixes:
            if key.startswith(prefix):
                entity = prefix.rstrip('_')
                field = key[len(prefix):]
                parties.setdefault(entity, {})[field] = row[key]
                keys_to_remove.append(key)
                break

    # Remove flat party fields
    for key in keys_to_remove:
        row.pop(key, None)

    # Add nested parties dict
    if parties:
        row['parties'] = parties

    return row


# --- Example 10: EDI 850 to CSV — Priority assignment with loop ------------
# Use with: sample_850.edi (EDI to CSV direction)
# Demonstrates loop-based computed columns and conditional logic

counter = {'n': 0}
priority_thresholds = [
    ('HIGH',   5000),
    ('MEDIUM', 1000),
    ('LOW',    0),
]

def apply_rules(row):
    counter['n'] += 1

    qty = float(row.get('quantity_ordered', 0))
    price = float(row.get('unit_price', 0))
    line_total = round(qty * price, 2)

    # Loop over priority thresholds to assign priority
    priority = 'LOW'
    for label, threshold in priority_thresholds:
        if line_total >= threshold:
            priority = label
            break

    # Format date
    date_raw = row.get('order_date', '')
    formatted_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}" if len(date_raw) == 8 else date_raw

    return {
        'row_num': counter['n'],
        'po_number': row.get('purchase_order_number', ''),
        'order_date': formatted_date,
        'buyer': row.get('BY_name', ''),
        'buyer_city': row.get('BY_city', ''),
        'ship_to': row.get('ST_name', ''),
        'ship_to_city': row.get('ST_city', ''),
        'supplier': row.get('SE_name', ''),
        'line_number': row.get('line_number', ''),
        'product_id': str(row.get('product_id', '')).strip(),
        'description': row.get('description', ''),
        'quantity': int(qty),
        'unit_price': round(price, 2),
        'line_total': line_total,
        'priority': priority,
    }


# --- Example 11: EDI — Nested loop to build lookup from parties ------------
# Use with: any EDI file (EDI to JSON direction)
# Demonstrates nested loops and list comprehensions

supplier_directory = {
    'TECH001': 'TechSupply Inc (US)',
    'ACME001': 'Acme Corporation (US)',
    'WH001':   'Warehouse West (US)',
}

def apply_rules(row):
    # Build list of all parties present in this row using a loop
    entities = []
    for prefix in ['BY', 'ST', 'SE', 'RE']:
        name_key = f"{prefix}_name"
        id_key = f"{prefix}_id_code"
        if row.get(name_key):
            entities.append({
                'role': prefix,
                'name': row[name_key],
                'id': row.get(id_key, ''),
                'directory_match': supplier_directory.get(row.get(id_key, ''), 'Not listed'),
            })

    # Add aggregated view
    row['all_parties'] = entities
    row['party_count'] = len(entities)
    row['party_names'] = ' | '.join(e['name'] for e in entities)

    # Clean up — remove individual party fields (already captured above)
    for key in list(row.keys()):
        if any(key.startswith(p + '_') for p in ['BY', 'ST', 'SE', 'RE', 'VN']):
            row.pop(key, None)

    return row


# --- Example 12: EDI 850 — While loop with accumulator --------------------
# Use with: sample_850.edi
# Demonstrates a while loop, though for-loop is usually preferred

def apply_rules(row):
    # Parse product ID components: e.g. "WIDGET-A-100" → parts
    product_id = str(row.get('product_id', ''))
    parts = product_id.split('-')

    # Build description pieces using a while loop
    pieces = []
    i = 0
    while i < len(parts):
        pieces.append(f"Part{i+1}={parts[i]}")
        i += 1

    row['product_parts'] = ' / '.join(pieces)
    row['product_prefix'] = parts[0] if parts else ''
    row['product_part_count'] = len(parts)

    return row


counter = {'n': 0}                                                                                                                                          
uom_map = {'EA': 'Each', 'CS': 'Case', 'BX': 'Box', 'PK': 'Pack'}
                                                                                                                                                            
def apply_rules(row):
    qty = int(row['quantity_ordered'])                                                                                                                      
    price = float(row['unit_price'])                      
                                                                                                                                                            
    row['product_id'] = str(row['product_id']).strip().upper()
    row['description'] = str(row['description']).strip()                                                                                                    
    counter['n'] += 1                                     
    row['item_no'] = counter['n']                                                                                                                           
    row['qty'] = qty
    row['price'] = price                                                                                                                                    
    row['line_total'] = round(qty * price, 2)             
    row['unit'] = uom_map.get(row.get('unit_of_measure', ''), 'Each')
    row['currency'] = 'USD'                                                                                                                                 

    order = ['item_no', 'product_id', 'description', 'qty', 'unit', 'price', 'line_total', 'currency']                                                      
    return {k: row.get(k, '') for k in order}