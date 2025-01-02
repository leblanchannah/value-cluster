from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from urllib.parse import parse_qs, urlparse
import requests
import selenium
from datetime import datetime
from typing import List, Tuple, Dict
import json
import re
import time
import sqlite3
import logging
logger = logging.getLogger(__name__)

BASE_URL = 'https://www.sephora.com'
CRAWL_DELAY=5
SCROLL_PAUSE_TIME = 0.2
CLICK_DELAY = 0.2
DRIVER_PATH = '../../../chrome-mac-x64/chromedriver'
DATA_DIR = "data/"

options = Options()
options.headless = True
options.add_argument("--window-size=1920,1200")
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36'
options.add_argument('user-agent={0}'.format(user_agent))


def execute_sql_query(db_file: str, sql_query: str):
    """
    Executes a given SQL query on the specified SQLite database.

    Args:
        db_file (str): Path to the SQLite database file.
        sql_query (str): The SQL query to execute.
    """
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        conn.commit()
        print("SQL query executed successfully.")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        if conn:
            conn.close()



def create_product_details_table(db_file):

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("""
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
                record_created TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(product_code)
            )
        """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        if conn:
            conn.close()

def insert_product_details_batch(db_file:str, products: List[Dict]):
    try:
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
                product.get("size_refinement"),
                datetime.now()
            )
            for product in products
        ]

        cursor.executemany(
            """
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            batch_data
        )

        conn.commit()
        print(f"{len(products)} records inserted into 'product_details'.")


    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    
    finally:
        # Close the connection
        if conn:
            conn.close()



def create_product_table(db_file):
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER,
            product_url TEXT,
            sku TEXT,
            product_code TEXT,
            record_created TIMESTAMP,
            FOREIGN KEY (brand_id) REFERENCES brands(brand_id)
        )
        """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    
    finally:
        # Close the connection
        if conn:
            conn.close()

def insert_brand_products_batch(db_file: str, brand_id: int, product_urls: List[str]):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        batch_data = [
            (brand_id, url, BrandPageScraper.extract_url_sku(url), BrandPageScraper.extract_url_product_code(url), datetime.now())
            for url in product_urls
        ]
        cursor.executemany(
            """
            INSERT INTO products (brand_id, product_url, sku, product_code, record_created)
            VALUES (?, ?, ?, ?, ?)
            """,
            batch_data
        )

        conn.commit()
        print(f"{len(product_urls)} records inserted into 'products'.")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

    finally:
        if conn:
            conn.close()



# Function to create the 'brands' table
def create_brands_table(db_file):
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Create the 'brands' table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name CHAR NOT NULL,
            brand_url CHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print("Table 'brands' created successfully.")
    
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    
    finally:
        # Close the connection
        if conn:
            conn.close()

# Function to insert data into the 'brands' table
def insert_brands_data(db_file, data):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Insert data into the 'brands' table
        for brand in data:
            cursor.execute("""
            INSERT INTO brands (brand_name, brand_url)
            VALUES (?, ?)
            """, (brand["brand_name"], brand["brand_url"]))
        
        # Commit the transaction
        conn.commit()
        print(f"{len(data)} records inserted into 'brands'.")
    
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    
    finally:
        # Close the connection
        if conn:
            conn.close()


class BrandPageScraper:
    def __init__(self, driver):
        self.driver = driver

    def get_product_urls(self, brand_url):
        self.driver.get(brand_url)
        product_urls = set()
        y_height = 0
        while True:
            current_height = self.driver.execute_script("return document.body.scrollHeight")
            product_urls.update(self._extract_visible_product_urls())
            scrolled_height = self._scroll_down(y_height)
            if not self._click_show_more_button() and current_height<=scrolled_height:
                break
            y_height = scrolled_height
        return list(product_urls)

    def _extract_visible_product_urls(self):
        # Locate all product links
        product_tiles = self.driver.find_elements(By.XPATH, '//a[contains(@href, "/ca/en/product/")]')
        return [tile.get_attribute('href') for tile in product_tiles]
    
    def _scroll_down(self, y_height, scroll_amount=1000):
        new_height = y_height + scroll_amount
        self.driver.execute_script(f"window.scrollTo(0, {new_height});")
        time.sleep(SCROLL_PAUSE_TIME)
        return new_height

    def _click_show_more_button(self):
        try:
            button = self.driver.find_element(By.XPATH, '//button[text()="Show More Products"]')
            button.click()
            time.sleep(CLICK_DELAY)
            return True
        except:
            return False
        
    @staticmethod
    def extract_url_sku(product_url):
        parsed_url = urlparse(product_url)
        query_params = parse_qs(parsed_url.query)
        sku = query_params.get("skuId", [None])[0]  # Default to None if not found
        return sku

    @staticmethod
    def extract_url_product_code(product_url):
        # Step 1: Parse the URL to get query parameters
        parsed_url = urlparse(product_url)
        match = re.search(r"-([A-Z0-9]+)$", parsed_url.path)
        product_code = match.group(1) if match else None
        return product_code

    
class BrandListScraper:
    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url

    def get_brand_urls(self):
        """Scrapes the main brand list to extract brand URLs."""
        brand_data = []
        self.driver.get(f"{self.base_url}")
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for brand_link in soup.findAll('a', attrs={"data-at": "brand_link"}):
            brand = {
                'brand_name': brand_link.span.text,
                'brand_url': brand_link.get('href') 
            }
            brand_data.append(brand)
        return brand_data

class ProductScraper:

    def __init__(self, driver):
        self.driver = driver

    @staticmethod
    def get_product_data_api(product_id):

        base_url = "https://www.sephora.com/api/v3/catalog/products/"
        request_url = f"{base_url}{product_id}?addCurrentSkuToProductChildSkus=true&includeRegionsMap=true&showContent=true&includeConfigurableSku=true&countryCode=CA&removePersonalizedData=true&includeReviewFilters=true&includeReviewImages=false&includeRnR=true&loc=en-CA&ch=rwd&sentiments=6"
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
        cookies = {'cookie_name': 'cookie_value'}
        session.get(BASE_URL, headers=headers, cookies=cookies)

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
        response = session.get(request_url, headers=headers)
        return response.json()
    
    @staticmethod
    def map_product_response_to_record(data):
        product_details = {
            'sku_id':data['skuId'], # str
            'brand_name':data['brandName'], # str
            'display_name':data['displayName'], # str
            'ingredients':data['ingredientDesc'], # str
            'limited_edition':data['isLimitedEdition'], # bool
            'first_access':data['isFirstAccess'], # bool
            'limited_time_offer':data['isLimitedTimeOffer'],# bool
            'new_product':data['isNew'],# bool
            'online_only':data['isOnlineOnly'],# bool
            'few_left':data['isOnlyFewLeft'],# bool
            'out_of_stock':data['isOutOfStock'],# bool
            'price':data['listPrice'], # str
            'max_purchase_quantity':data['maxPurchaseQuantity'], # int
            'size':data['size'], # str
            'type':data['type'], # str
            'url':data['url'],# str
            'variation_description':data['variationDesc'],# str
            'variation_type':data['variationType'],# str
            'variation_value':data['variationValue'],# str
            'returnable':data['isReturnable'], #bool
            'finish_refinement':"", # str
            'size_refinement':"" # str
        }

        if 'finishRefinements' in data['refinements'].keys():
            product_details['finish_refinement'] = ' '.join(data['refinements']['finishRefinements'])

        if 'sizeRefinements' in data['refinements'].keys():
            product_details['size_refinement'] = ' '.join(data['refinements']['sizeRefinements'])

        return product_details

    @staticmethod
    def compress_product_data(data):
        product_variations = []
        parent_sku = {
            'target_url':data['targetUrl'],
            'product_id':data['productId'],
            'loves_count':data['productDetails']['lovesCount'],
            'rating':data['productDetails']['rating'],
            'reviews':data['productDetails']['reviews'],
            'brand_id':data['productDetails']['brand']['brandId'],
            'category_root_id':data['parentCategory']['categoryId'],
            'category_root_name':data['parentCategory']['displayName'],
            'category_root_url':data['parentCategory']['url'],
            'category_child_id':data['parentCategory']['parentCategory']['categoryId'],
            'category_child_name':data['parentCategory']['parentCategory']['displayName'],
            'category_child_url':data['parentCategory']['parentCategory']['url'],
            'category_grandchild_id':data['parentCategory']['parentCategory']['parentCategory']['categoryId'],
            'category_grandchild_name':data['parentCategory']['parentCategory']['parentCategory']['displayName'],
            'category_grandchild_url':data['parentCategory']['parentCategory']['parentCategory']['url'],
        }

        product_details = ProductScraper.map_product_response_to_record(data['currentSku'])
        product_variations.append({**parent_sku, **product_details})

        for child_sku in data['regularChildSkus']:
            product_details = ProductScraper.map_product_response_to_record(child_sku)
            product_variations.append({**parent_sku, **product_details})

        return product_variations


    def get_product_data_scrape(self, url):
        #TODO not tested since update to using api for product details
        product = {}
        self.driver.get(url)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        try:
            h1 = soup.h1.text
        except Exception as e:
            print(f"An error occurred: {e}")
            return product
        if h1=='Sorry, this product is not available.' or h1=='Sorry! The page you’re looking for cannot be found.' or h1=="Search Results":
            product['error'] = "Product not available"  
        else:
            product["product_name"] = self._get_product_name(soup)
            product["brand_name"] = self._get_brand_name(soup)
            product["options"] = self._get_product_buttons()
            product["rating"], product["product_reviews"] = self._get_rating_data(soup)
            product["ingredients"] = self._get_ingredients(soup)
            product["n_loves"] = self._get_num_loves(soup)
            product["categories"] = self._get_breadcrumb_categories(soup)
        return product

    def _get_sku(self, soup):
        #TODO not tested since update to using api for product details
        """
        Returns sku code from product page in format 'Item #######'
        SKU can also be found in product URL 
        """
        sku_element = soup.find('p', attrs={'data-at': 'item-sku'})
        if sku_element:
            return sku_element.text.strip() 
        
    def _get_breadcrumb_categories(self, soup) -> List:
        #TODO not tested since update to using api for product details
        """
        Returns list of categorical values used to describe product in header of product page
            for ex. ['Skincare','Moisturizer',...] at time of web scraping there are max of three levels in breadcrumbs
        """
        return [x.text for x in soup.find('nav', attrs={'data-comp':"ProductBreadCrumbs BreadCrumbs BreadCrumbs "}).findAll('li')]
    
    def _get_brand_name(self, soup) -> str:
        #TODO not tested since update to using api for product details
        """
        Returns product brand name from product page
        """
        a_tag = soup.find("a", attrs={'data-at':"brand_name"})
        if a_tag:
            return a_tag.text
       
    def _get_product_name(self, soup) -> str:
        #TODO not tested since update to using api for product details
        """
        Returns product name as written on product page
        """
        span_tag = soup.find("span", attrs={'data-at': "product_name"})
        if span_tag:
            return span_tag.text

    def _get_num_loves(self, soup) -> str:
        #TODO not tested since update to using api for product details
        """
        Returns number of 'love' votes for product
            loves seem to be used to track product frequently repurchased
        """
        span_tag = soup.find("div", attrs={"data-comp": "LovesCount "}).span
        if span_tag:
            return span_tag.text

    def _get_product_flag_label(self) -> str:
        #TODO not tested since update to using api for product details
        flag_label = self.driver.find_element(By.XPATH, "//span[@data-at='product_flag_label']")
        if flag_label:
            return flag_label.text
        
    def _get_ingredients(self, soup) -> str:
        #TODO not tested since update to using api for product details
        """
        Returns full ingredient list as a blob of text
        """
        div_ig = soup.find("div", {"id": "ingredients"})
        if div_ig:
            return div_ig.text

    def _get_rating_data(self, soup) -> Tuple[str, str]:
        #TODO not tested since update to using api for product details
        """
            Sephora product page displays a 1-5 bar histogram of votes but it is difficult to retrieve the histogram data
            ******might be able to figure this out later
            Returns star rating and number of reviews as tuple
        """
        rr_container = soup.find("a", {"href": "#ratings-reviews-container"})
        if rr_container:
            star_rating = rr_container.find('span', attrs={'data-at': 'star_rating_style'})['style']
            num_reviews = rr_container.text
            return star_rating, num_reviews

    def _get_product_buttons(self, click_delay=CLICK_DELAY) -> Dict:
        #TODO not tested since update to using api for product details
        """
        Products can have size and colour variations on product pages. Each product option available must be clicked
        on product page to update price.
        The data produced by this function are messy because product volume formats can look very different depending on brand.
        Additionally, this function needs to be improved to capture both original and sale prices if a product is on sale.

        """
        product_options = []
        # swatch group shows product options within category
        for swatch_grp in self.driver.find_elements(By.XPATH, "//div[@data-comp='SwatchGroup ']"):
            buttons = swatch_grp.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                time.sleep(click_delay)
                try:
                    button.click()
                except Exception as e:
                    print(f"An error occurred: {e}")
                    print('reached non-clickable web element')
                    return product_options
                product_info = {}
                product_info['swatch_group'] = swatch_grp.find_element(By.TAG_NAME, "p").text
                product_info["flag_label"] = self._get_product_flag_label()
                try:
                    product_info['size'] = self.driver.find_element(By.XPATH, "//span[@data-at='sku_size_label']").text
                except Exception as e:
                    print(f"An error occurred: {e}")
                    product_info['size'] = None
                try:
                    product_info['name'] = [x.text for x in self.driver.find_elements_by_xpath("//div[@data-at='sku_name_label']//span")]
                except Exception as e:
                    print(f"An error occurred: {e}")
                    product_info['name'] = None
                # if item is on sale, there will be two b tags, first is sale, second is original price
                product_info['price'] = [b.text for b in self.driver.find_elements(By.XPATH, "//p[@data-comp='Price ']//b")]
                product_info['sku'] = self.driver.find_element(By.XPATH, "//p[@data-at='item_sku']").text
                product_options.append(product_info)
        return product_options


if __name__ == "__main__":

    DB_FILE = "../data/db/products.db"

    # create tables 
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
        record_created TIMESTAMP,
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
        record_created TIMESTAMP
    )
    """

    execute_sql_query(DB_FILE, create_brands_table_query)
    execute_sql_query(DB_FILE, create_products_table_query)
    execute_sql_query(DB_FILE, create_product_details_table_query)

    brand_urls = []
    brand_list_url = 'https://www.sephora.com/ca/en/brands-list'
    with webdriver.Chrome(options=options) as driver:
        brands = BrandListScraper(driver, brand_list_url)
        brand_urls = brands.get_brand_urls()


    insert_brands_data(DB_FILE, brand_urls)
    for brand in brand_urls:
        time.sleep(5)
        with webdriver.Chrome(options=options) as driver:
            brand_page = BrandPageScraper(driver)
            try:
                product_urls = brand_page.get_product_urls(brand['brand_url'])
            except selenium.common.exceptions.InvalidArgumentException as e:
                print(f"SQLite error: {e}")
                print(brand['brand_url'])
                continue


            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("""SELECT id FROM brands where brand_url=?""", (brand['brand_url'],))
                brand_id = cursor.fetchone()
            except sqlite3.Error as e:
                print(f"SQLite error: {e}")
            finally:
                if conn:
                    conn.close()

                insert_brand_products_batch(DB_FILE, brand_id, product_urls)

    # example_product = "https://www.sephora.com/ca/en/product/bondi-boost-rapid-repair-bond-builder-leave-in-hair-for-damaged-hair-P513096?skuId=2791291&icid2=products%20grid:p513096:product"

    # sku = BrandPageScraper.extract_url_sku(example_product)
    # product_code = 'P384963'
    # product_data_sample = ProductScraper.get_product_data_api(product_code)
    # with open('../data/product_sample_multiple_skus.json', 'w') as f:
    #     json.dump(product_data_sample, f)

    # insert_product_details(DB_FILE, ProductScraper.compress_product_data(product_data_sample))

    # import pandas as pd
    # data = pd.DataFrame(ProductScraper.compress_product_data(product_data_sample))
    # print(data.columns)
    # data.to_csv('../data/product_details_sample.csv')