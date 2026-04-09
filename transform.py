
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


from datetime import datetime, timedelta                                                                                                                    
import math                                               
def apply_rules(row):
    row['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row['date_only'] = datetime.now().strftime('%d/%m/%Y')
    row['tomorrow'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')                                                                             
    row['price_sqrt'] = round(math.sqrt(float(row['price'])), 2)
    return row


counter = {'n': 0}                                                                                                                                          
                                                            
def apply_rules(row):
    counter['n'] += 1
    row['serial_no'] = counter['n']                                                                                                                         
    return row


counter = {'n': 0}
def apply_rules(row):
    counter['n']+=1
    row['serial_no'] = counter['n']
    renames = {'name': 'product_name', 'brand': 'manufacturer'}
    row = {renames.get(k, k): v for k, v in row.items()}
    order = ['serial_no', 'id', 'product_name', 'manufacturer', 'price']
    return {k: row[k] for k in order if k in row}
