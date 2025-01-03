
from typing import List, Dict
import sqlite3
import logging
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db_operations.log"),  # Logs to a file
        logging.StreamHandler()  # Logs to the console
    ]
)

def execute_sql_query(db_file: str, sql_query: str, table_name: str):
    """
    Executes a given SQL query on the specified SQLite database.

    Args:
        db_file (str): Path to the SQLite database file.
        sql_query (str): The SQL query to execute.
        table_name (str):
    """
    try:
        logging.info(f"Connecting to database: {db_file}")
        conn = sqlite3.connect(db_file)

        cursor = conn.cursor()
        logging.info(f"Executing SQL query for table: {table_name or 'unknown'}")
        logging.debug(f"SQL Query: {sql_query}")

        cursor.execute(sql_query)
        conn.commit()
        logging.info(f"SQL query executed successfully for table: {table_name or 'unknown'}")

    except sqlite3.Error as e:
        logging.error(f"SQLite error occurred for table {table_name or 'unknown'}: {e}")
        raise 
    finally:
        if conn:
            conn.close()
            logging.info(f"Database connection closed for table: {table_name or 'unknown'}")


def insert_product_details_batch(db_file:str, products: List[Dict], table_name: str):
    try:
        logging.info(f"Connecting to database: {db_file}")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        batch_data = [
            (
                product.get("target_url"),
                product.get("product_id"),
                product.get("loves_count"),
                product.get("rating"),
                product.get("reviews"),
                product.get("brand_source_id"),
                product.get("category_root_id"),
                product.get("category_root_name"),
                product.get("category_root_url"),
                product.get("category_child_id"),
                product.get("category_child_name"),
                product.get("category_child_url"),
                product.get("category_grandchild_id"),
                product.get("category_grandchild_name"),
                product.get("category_grandchild_url"),
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
                product.get("variation_description"),
                product.get("variation_type"),
                product.get("variation_value"),
                product.get("returnable"),
                product.get("finish_refinement"),
                product.get("size_refinement")
            )
            for product in products
        ]

        sql_query = """
            INSERT INTO product_details (
                target_url, product_id, loves_count, rating, reviews, brand_source_id,
                category_root_id, category_root_name, category_root_url,
                category_child_id, category_child_name, category_child_url,
                category_grandchild_id, category_grandchild_name, category_grandchild_url,
                sku_id, brand_name, display_name, ingredients, limited_edition,
                first_access, limited_time_offer, new_product, online_only,
                few_left, out_of_stock, price, max_purchase_quantity, size, type,
                url, variation_description, variation_type, variation_value,
                returnable, finish_refinement, size_refinement, record_created
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """

        logging.info(f"Executing SQL query for table: {table_name or 'unknown'}")
        logging.debug(f"SQL Query: {sql_query}")

        cursor.executemany(sql_query, batch_data)
        conn.commit()

        logging.info(f"""SQL query executed successfully for table: {table_name or 'unknown'},
                    {len(products)} rows inserted""")

    except sqlite3.Error as e:
        logging.error(f"SQLite error occurred for table {table_name or 'unknown'}: {e}")
        raise 
    
    finally:
        if conn:
            conn.close()
            logging.info(f"Database connection closed for table: {table_name or 'unknown'}")



def insert_brand_products_batch(db_file: str, brand_id: int, batch_data: List[str], table_name: str):
        logging.info(f"Connecting to database: {db_file}")
        conn = sqlite3.connect(db_file, timeout=10)
        cursor = conn.cursor()

        sql_query = """
            INSERT INTO products (brand_id, product_url, sku, product_code)
            VALUES (?, ?, ?, ?)
            """
            # ON CONFLICT DO NOTHING 
        logging.info(f"Executing SQL query for table: {table_name or 'unknown'}")
        logging.debug(f"SQL Query: {sql_query}")

        for product in batch_data:
            try:
                cursor.execute(sql_query, product)
                conn.commit()
                logging.info(f"Row inserted successfully: {product}")

            except sqlite3.Error as row_error:
                conn.rollback()
                logging.error(f"Error inserting row: {product}. SQLite error: {row_error}")
                continue

        if conn:
            conn.close()
            logging.info("Database connection closed.")


# Function to insert data into the 'brands' table
def insert_brands_data_batch(db_file: str, data: List, table_name:str):
    try:
        logging.info(f"Connecting to database: {db_file}")

        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        batch_data = [(brand["brand_name"], brand["brand_url"]) for brand in data]

        sql_query = """ INSERT INTO brands (brand_name, brand_url) VALUES (?, ?)"""
        logging.info(f"Executing SQL query for table: {table_name or 'unknown'}")
        logging.debug(f"SQL Query: {sql_query}")
        
        cursor.executemany(sql_query, batch_data)
        conn.commit()

        logging.info(f"""SQL query executed successfully for table: {table_name or 'unknown'},
                    {len(batch_data)} rows inserted""")
    except sqlite3.Error as e:
        logging.error(f"SQLite error occurred for table {table_name or 'unknown'}: {e}")
        raise 
    finally:
        if conn:
            conn.close()
            logging.info(f"Database connection closed for table: {table_name or 'unknown'}")


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
    product_id TEXT,
    loves_count INTEGER,
    rating REAL,
    reviews INTEGER,
    brand_source_id INTEGER,
    category_root_id TEXT,
    category_root_name TEXT,
    category_root_url TEXT,
    category_child_id TEXT,
    category_child_name TEXT,
    category_child_url TEXT,
    category_grandchild_id TEXT,
    category_grandchild_name TEXT,
    category_grandchild_url TEXT,
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
    variation_description TEXT,
    variation_type TEXT,
    variation_value TEXT,
    returnable BOOLEAN,
    finish_refinement TEXT,
    size_refinement TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""