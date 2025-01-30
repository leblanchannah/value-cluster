from typing import List, Dict, Tuple
import sqlite3
import logging

# TODO backup db before insert 
# TODO error logs
# CREATE TABLE IF NOT EXISTS error_logs (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     row_data TEXT,
#     error_message TEXT,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

# TODO Integrate email or webhook notifications to alert of: Successful runs. Issues like failed rows or missing tables.


logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db_operations.log"),  # Logs to a file
        logging.StreamHandler()  # Logs to the console
    ]
)

logger = logging.getLogger(__name__)


def get_db_connection(db_file: str):
    """Context manager for SQLite database connection.

    Yields:
        conn: sqlite3 database connection
    """
    try:
        logger.info(f"Connecting to database: {db_file}")
        conn = sqlite3.connect(db_file, timeout=10)
        return conn
    finally:
        logger.info(f"Database connection closed.")


def execute_query(db_file: str, sql_query: str, params: Tuple = ()):
    """Executes a single SQL query.

    Args:
        db_file (str): _description_
        sql_query (str): _description_
        params (Tuple, optional): _description_. Defaults to ().
    """
    try:
        with get_db_connection(db_file) as conn:
            cursor = conn.cursor()
            logger.debug(f"Executing query: {sql_query} | Params: {params}")
            cursor.execute(sql_query, params)
            conn.commit()
            logger.info("SQL query executed successfully.")
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
        raise


def insert_batch(db_file: str, sql_query: str, batch_data: List[Tuple]):
    """Executes a batch insert into the database.

    Args:
        db_file (str): _description_
        sql_query (str): _description_
        batch_data (List[Tuple]): _description_
    """
    logger.info(batch_data)
    try:
        with get_db_connection(db_file) as conn:
            cursor = conn.cursor()
            logger.debug(f"Executing batch insert: {sql_query} | Batch size: {len(batch_data)}")
            cursor.executemany(sql_query, batch_data)
            conn.commit()
            logger.info(f"Batch insert successful. {len(batch_data)} rows inserted.")
    except sqlite3.Error as e:
        logger.error(f"Batch insert error: {e}")
        raise


def insert_product_details(db_file:str, products: List[Dict], table_name: str):
    """
    Args:
        db_file: (str)
        products: (List[Dict])
        table_name: str
    """
    sql_query = """
        INSERT INTO product_details (
            target_url, full_product_url, product_code, loves_count, rating, reviews, brand_source_id,
            category_id, category_name, category_url,
            sku_id, brand_name, display_name, ingredients, limited_edition,
            first_access, limited_time_offer, new_product, online_only,
            few_left, out_of_stock, price, max_purchase_quantity, size, type,
            url, variation_type, variation_value,
            returnable, finish_refinement, size_refinement, short_description, long_description,
            suggested_usage
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """
    batch_data = [(
            product.get("target_url"),
            product.get("full_product_url"),
            product.get("product_code"),
            product.get("loves_count"),
            product.get("rating"),
            product.get("reviews"),
            product.get("brand_id"),
            product.get("category_id"),
            product.get("category_name"),
            product.get("category_url"),
            product.get("sku_id"),
            product.get("brand_name"),
            product.get("display_name"),
            product.get("ingredients"),
            product.get("limited_edition"),
            product.get("first_access"),
            product.get("limited_time_offer"),
            product.get("new_product"),
            product.get("online_only"),
            product.get("few_left"),
            product.get("out_of_stock"),
            product.get("price"),
            product.get("max_purchase_quantity"),
            product.get("size"),
            product.get("type"),
            product.get("url"),
            product.get("variation_type"),
            product.get("variation_value"),
            product.get("returnable"),
            product.get("finish_refinement"),
            product.get("size_refinement"),
            product.get("short_description"),
            product.get("long_description"),
            product.get("suggested_usage") 
        ) for product in products]
    
    insert_batch(db_file, sql_query, batch_data)


def insert_brand_products(db_file: str, brand_id: int, data: List[str], table_name: str):
    """Inserts brand products into the database scraped from brand pages.
    Product urls used in downstream API calls to get product details.
    Args:
        db_file: (str)
        data: (List[Dict])
        table_name: str
    """

    sql_query = """
        INSERT INTO products (brand_id, product_url, sku, product_code)
        VALUES (?, ?, ?, ?)
    """
    # insert_batch(db_file, sql_query, [(brand_id, *data) for data in data])
    insert_batch(db_file, sql_query, [(data) for data in data])


# Function to insert data into the 'brands' table
def insert_brands_data(db_file: str, data: List, table_name:str):
    """Inserts brand data into the database.
    Args:
        db_file: (str)
        data: (List[Dict])
        table_name: str
    """
    sql_query = """INSERT INTO brands (brand_name, brand_url) VALUES (?, ?)"""
    batch_data = [(brand["brand_name"], brand["brand_url"]) for brand in data]
    insert_batch(db_file, sql_query, batch_data)


create_brands_table_query = """
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name CHAR NOT NULL,
    brand_url CHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

create_products_table_query = """
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER,
    product_url TEXT,
    sku TEXT,
    product_code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (brand_id) REFERENCES brands(id)
)
"""

create_product_details_table_query = """
CREATE TABLE IF NOT EXISTS product_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_url TEXT,
    full_product_url TEXT,
    product_code TEXT,
    loves_count INTEGER,
    rating REAL,
    reviews INTEGER,
    brand_source_id INTEGER,
    category_id TEXT,
    category_name TEXT,
    category_url TEXT,
    sku_id TEXT,
    brand_name TEXT,
    display_name TEXT,
    ingredients TEXT,
    limited_edition BOOLEAN,
    first_access BOOLEAN,
    limited_time_offer BOOLEAN,
    new_product BOOLEAN,
    online_only BOOLEAN,
    few_left BOOLEAN,
    out_of_stock BOOLEAN,
    price TEXT,
    max_purchase_quantity INTEGER,
    size TEXT,
    type TEXT,
    url TEXT,
    variation_type TEXT,
    variation_value TEXT,
    returnable BOOLEAN,
    finish_refinement TEXT,
    size_refinement TEXT,
    short_description TEXT, 
    long_description TEXT,
    suggested_usage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_code) REFERENCES products(product_code)
)
"""