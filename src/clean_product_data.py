import glob
import json
import pandas as pd
import re
from webscraper import parse_url_info, drop_duplicate_product_urls


def expand_product_options(df):
    '''
    options for each product in list of dictionaries,
    expands each option to be its own row
    '''
    product_options = []
    for product in df.iterrows():
        url = product[1]['url']
        df_options = pd.json_normalize(product[1]['options'])
        df_options['url'] = url
        product_options.append(df_options)

    return df.merge(pd.concat(product_options), how='left', on='url')


def read_data(data_dir):
    '''
    V1 of scraped data in - data/products/*
    returns all json product files 
    '''
    files = glob.glob(data_dir)
    products = []
    for brand in files:
        with open(brand) as file:
            products.append(pd.json_normalize(json.loads(file.read())))
    
    return pd.concat(products, axis=0)
    

def shorthand_numeric_conversion(count_val):
    '''
    amount of loves or reviews is in format 3.2K or 1.1M for example
    '''
    if count_val:
        count_val = count_val.replace(".","")
        count_val = count_val.replace("K","00")
        count_val = count_val.replace("M","000000")
        count_val = float(count_val)
    return count_val


def clean_product_rating(rating):
    '''
    Expects format "Width: %00.00"
    puts rating on scale of 0-5, although no products have score < 1
    '''
    if rating:
        rating = rating.replace("width:","")
        rating = rating.replace("%","")
        rating = float(rating)/100*5
    return rating

def pre_parse_product_size_clean(input_string):
    '''
    '''
    input_string = input_string.strip()
    if len(input_string)<1:
        return None
    if input_string[0] == '.':
        input_string = "0"+input_string
    input_string = input_string.replace(" .","0.")
    input_string = input_string.replace("fl oz","floz")
    input_string = input_string.replace("fl. oz","floz")
    input_string = input_string.replace("oz.","oz")
    return input_string


def parse_volume_string(input_string):
    
    '''
    volume formatted like "misc string amount_a unit_a \ amount_b unit_b misc text"
    '''
    if not input_string:
        return None
    pattern = r'(?:(\d+(?:\.\d+)?)\s*([a-zA-Z]+))?\s*(?:(\d+(?:\.\d+)?)\s*([a-zA-Z]+))?\s*(.*)'
    match = re.match(pattern, input_string)
    if match:
        amount_a, unit_a, amount_b, unit_b, trailing_text = match.groups()
        return amount_a, unit_a, amount_b, unit_b, trailing_text
    return None,"",None,"",input_string


def parse_single_volume(input_string):
    '''
    case where volume is only shown in one measurement system
    '''
    pattern = r'\s*(\d+(\.\d*)?|\.\d+)\s*(\w+)\s*'
    matches = re.match(pattern, input_string)
    if matches:
        amount = matches.group(1)
        unit = matches.group(3)
        return amount, unit
    return None


def split_product_multiplier(input_string):
    '''
    '''
    if not input_string:
        return [None,None]
    if " x" not in input_string:
        return [None, input_string]
    input_string = input_string.split(" x", 1)
    if len(input_string)==1:
        input_string = [None] + input_string
    return input_string



def main():

    df_products = read_data("../data/products/*")

    df_products = df_products[df_products['product_name'].notnull()]
    df_products = df_products.reset_index(drop=True).reset_index().rename(columns={'index':'internal_product_id'})

    df_products = expand_product_options(df_products)

    # string col to lower removed 'product_name', and brand_nme
    cols_to_lower = [ 'swatch_group', 'size', 'name']
    df_products[cols_to_lower] = df_products[cols_to_lower].apply(lambda x: x.str.lower())

    df_products['rating'] = df_products['rating'].apply(clean_product_rating)

    df_products['n_loves'] = df_products['n_loves'].apply(shorthand_numeric_conversion)

    df_products['product_reviews'] = df_products['product_reviews'].apply(shorthand_numeric_conversion)

    df_products['price'] = df_products['price'].str.replace("$","")
    df_products['price'] = df_products['price'].astype(float)

    df_products['sku'] = df_products['sku'].str.replace("Item ","")

    # this will change in V2 of scraped data
    df_products['out_of_stock'] = df_products['name'].str.contains('out of stock')
    df_products['limited_edition'] = df_products['name'].str.contains('limited edition')
    df_products['new_product'] = df_products['name'].str.contains('new')
    df_products['few_left'] = df_products['name'].str.contains('only a few left')
    df_products['sale'] = df_products['name'].str.contains('sale')
    df_products['refill'] = df_products['name'].str.contains('refill')

    # categories from bread crumbs, starts with list of 3 categorical values
    # fill value is '   ', list of 3 empty spaces
    df_products['categories'] = df_products['categories'].fillna('   ')
    df_products['lvl_0_cat'], df_products['lvl_1_cat'], df_products['lvl_2_cat'] = df_products['categories'].str
    df_products['lvl_2_cat'] = df_products['lvl_2_cat'].fillna("")
    # removing sets entirely from dataset
    df_products = df_products[~df_products['lvl_2_cat'].str.contains("Sets")]

    df_products['url_path'], df_products['url_sku'], df_products['url_params'] =  df_products['url'].apply(parse_url_info).str

    # dropping duplicate products 
    df_products = df_products.drop_duplicates(subset=['brand_name','product_name','url_path', 'sku','price'], keep='last')

    df_products.loc[df_products['size'].isna(), 'size'] = df_products['name']
    df_products.loc[df_products['size']==df_products['name'],'name'] = None

    def series_replace(df, ids):
        for key in ids.keys():
            df['size'] = df['size'].str.replace(key, ids[key], regex=True)
        return df

    misc_text = {
        "out of stock":"",
        "limited edition":"",
        "new":"",
        "only a few left":"",
        "sale":"",
        "size":"",
        "refill":"",
        "color":"",
        ":":"",
        "-":"",
        "mini":"",
        " oz.":" oz",
        "/":" ",
        r'\s+': ' '
    }

    df_products = series_replace(df_products, misc_text)
    df_products['size'] = df_products['size'].fillna("")
    df_products['size'] = df_products['size'].apply(pre_parse_product_size_clean)

    df_products['product_multiplier'] = df_products['size'].apply(split_product_multiplier)
    temp = pd.DataFrame(df_products['product_multiplier'].tolist(), columns=['multiplier','m_size'])
    df_products = pd.concat([df_products, temp], axis=1)
    df_products.loc[df_products['multiplier'].notnull(), 'size']= df_products['m_size']
    df_products.loc[:,'product_multiplier']= df_products['multiplier']


    df_products = df_products.drop(['multiplier','m_size'], axis=1)
    df_products['product_multiplier'] = pd.to_numeric(df_products['product_multiplier'], errors='coerce')
    df_products['product_multiplier'] = df_products['product_multiplier'].fillna(1.0)
    df_products['size'] = df_products['size'].astype(str)
    df_products['amount_a'], df_products['unit_a'], df_products['amount_b'], df_products['unit_b'], df_products['misc_info'] = df_products['size'].apply(parse_volume_string).str
    df_products[['amount_a','amount_b']] = df_products[['amount_a','amount_b']].astype(float)

    df_products['amount_single'], df_products['unit_single'] = df_products[df_products['amount_a'].isna()]['size'].apply(parse_single_volume).str
    df_products['amount_single']= df_products['amount_single'].astype(float)

    df_products.loc[df_products['amount_a'].isna(), 'amount_a'] = df_products['amount_single']
    df_products.loc[df_products['amount_a'].isna(), 'unit_a'] = df_products['unit_single']
    df_products = df_products.drop(['amount_single','unit_single'],axis=1)

    # only allow products in formats floz, oz, g, ml
    df_products = df_products[df_products['unit_a'].isin(['floz','oz'])]
    df_products = df_products[df_products['unit_b'].isin(['g','ml','mg','l','kg'])]
    df_products.loc[(df_products['unit_a']=='fl'),'unit_a']='floz'

    # swatch_group, additional info parsed into column 'swatch_details'

    df_products['swatch_details'] = df_products['swatch_group'].str.split(" - ").str[0]
    df_products['swatch_group'] = df_products['swatch_group'].str.split(" - ").str[-1]

    df_products[['url_path','product_id']] = df_products['url_path'].str.split("-P", expand=True)

    df_products.to_csv('../data/processed_prod_data.csv', index=False)

    df = df_products.groupby(['product_id','product_name', 'brand_name', 'swatch_group','amount_a'], as_index=False).agg({
        'unit_a':'first',
        'price':'max',
        'internal_product_id':'nunique',
        'rating':'max',
        'product_reviews':'max',
        'n_loves':'max',
        'lvl_0_cat':'first',
        'lvl_1_cat':'first',
        'lvl_2_cat':'first',
        'sku':'unique',
        'amount_b':'first',
        'unit_b':'first',
        'product_multiplier':'first'
    })

    df['amount_adj'] = df['amount_a'] * df['product_multiplier'].astype('float')
    df['unit_price'] = df['price']/df['amount_adj']

    df = df.sort_values(by=['product_id', 'amount_adj'], ascending=True)
    df = df.drop_duplicates(subset=['product_id', 'price', 'swatch_group'], keep='last')

    df['prod_size_rank'] = df['amount_adj'].rank(method='first')
    df = df.reset_index()

    df.to_csv('../data/agg_prod_data.csv', index=False)

if __name__ == "__main__":
    main()
