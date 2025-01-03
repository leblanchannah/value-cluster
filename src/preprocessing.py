import sqlite3
import pandas as pd
from urllib.parse import urlparse, parse_qs
import re
import numpy as np


def clean_compressed_product_hierarchy(df, col, delimiter=' --- ', code_prefix_to_strip='cat'):
    clean_col = df[col].str.replace(code_prefix_to_strip,"")
    clean_col = clean_col.str.split(delimiter)
    clean_col = clean_col.apply(lambda x : x[::-1])
    return pd.DataFrame(clean_col.to_list(), columns=[f'{col}_l1', f'{col}_l2', f'{col}_l3'])


def parse_parent_code_from_url(url):
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    return params.get('parentProduct', [None])


def clean_missing_zero_sizes(size_string):
    """
    Adds a leading zero to decimal numbers missing it in the input string.
    Example: '.28oz' -> '0.28oz'
    """
    # Regular expression to find decimals missing leading zeros
    corrected_string = re.sub(r'(?<!\d)\.(\d+)', r'0.\1', size_string)
    return corrected_string

# Updated size parsing function
def parse_size_data(entry):
    # Preprocess to fix missing zeros
    entry = clean_missing_zero_sizes(entry)
    
    # Define patterns
    size_pattern = r'(\d+(?:\.\d+)?)\s*(oz|ml|g|lb|kg)'
    description_pattern = r'^(.*?)-'

    # Extract sizes and units
    sizes = re.findall(size_pattern, entry)
    description = re.search(description_pattern, entry)

    return {
        "sizes": sizes,  # List of all (value, unit) pairs
        "description": description.group(1).strip() if description else None
    }

# def parse_size_data(entry):
#     size_pattern = r'(\d+(?:\.\d+)?)\s*(oz|ml|g|lb|kg|l)'
#     description_pattern = r'^(.*?)-'

#     sizes = re.findall(size_pattern, entry)
#     description = re.search(description_pattern, entry)
    
#     return {
#         "sizes": sizes,  # List of all (value, unit) pairs
#         "description": description.group(1).strip() if description else None
#     }


def split_sizes(size_list):
    "flatten tuple lists of sizes and units into separate cols"
    flat_list = [item for sublist in size_list for item in sublist]  # Flatten the list of tuples
    return flat_list


def common_unit_cols(df, unit_col, size_col):
    df.loc[df[unit_col]=='g','unit_g'] = df[size_col]
    df.loc[df[unit_col]=='ml','unit_ml'] = df[size_col]
    df.loc[df[unit_col]=='oz','unit_oz'] = df[size_col]


if __name__ == "__main__":
    DB_FILE = "../data/db/products.db"
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM product_details", conn)
    conn.close()

    df = pd.concat([
        df, 
        clean_compressed_product_hierarchy(df, 'category_root_id', delimiter=' --- ', code_prefix_to_strip='cat'),
        clean_compressed_product_hierarchy(df, 'category_root_name', delimiter=' --- ', code_prefix_to_strip=''),
        clean_compressed_product_hierarchy(df, 'category_root_url', delimiter=' --- ', code_prefix_to_strip='/shop/')
    ], axis=1)

    df = df.drop(['category_root_id', 'category_root_name', 'category_root_url'], axis=1)

    df['parent_product_code'] = df['url'].apply(lambda x : parse_parent_code_from_url(x)[0])

    df['price'] = df['price'].str.strip('$').astype(float)

    df['size'] = df['size'].str.lower()
    df_size = pd.DataFrame.from_records(df['size'].apply(parse_size_data))
    max_pairs = df_size["sizes"].apply(len).max()  # Determine the maximum number of size-unit pairs

    for i in range(max_pairs):
        df_size[f"size_{i+1}"] = df_size["sizes"].apply(lambda x: x[i][0] if i < len(x) else None)
        df_size[f"unit_{i+1}"] = df_size["sizes"].apply(lambda x: x[i][1] if i < len(x) else None)

    # Drop the original "sizes" column if needed
    df_size.drop(columns=["sizes"], inplace=True)

    df = pd.concat([df, df_size], axis=1)

    unit_cols = ['unit_1','unit_2','unit_3','unit_4']
    size_cols = ['size_1','size_2','size_3','size_4']

    # dropping products with no size data
    df = df[~df[size_cols].isna().all(axis=1)]

    df[size_cols] = df[size_cols].astype(float)

    df.loc[df['unit_2'] == 'l', 'size_2'] = df['size_2'].astype(float)*1000.0
    df.loc[df['unit_2'] == 'l', 'unit_2'] = 'ml'

    df['unit_g'] = np.nan
    df['unit_ml'] = np.nan
    df['unit_oz'] = np.nan

    common_unit_cols(df, 'unit_1', 'size_1')
    common_unit_cols(df, 'unit_2', 'size_2')

    print(f"found (g) {df[df['unit_g'].notnull()].shape[0]}")
    print(f"found (ml) {df[df['unit_ml'].notnull()].shape[0]}")
    print(f"found (oz) {df[df['unit_oz'].notnull()].shape[0]}")

    conversion_oz_ml = 29.574
    df.loc[(df['unit_ml'].isna()) & (df['unit_oz'].notnull()), 'unit_ml'] = df['unit_oz']*conversion_oz_ml

    df['value_CAD_oz'] = df['price'] / df['unit_oz'] 
    df['value_CAD_ml'] = df['price'] / df['unit_ml'] 
    df['value_CAD_g'] = df['price'] / df['unit_g'] 

    df.to_csv('../data/preprocessed_data.csv', index=False)