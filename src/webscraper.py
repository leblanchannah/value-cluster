from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import InvalidArgumentException, NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains



from urllib.parse import urlsplit, parse_qs
import pandas as pd
from datetime import datetime
from typing import List, Tuple, Dict
import time
import json

BASE_URL = 'https://www.sephora.com'
CRAWL_DELAY=5
SCROLL_PAUSE_TIME = 0.2
CLICK_DELAY = 0.2
DRIVER_PATH = '../../../chromedriver_mac64/chromedriver'
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

import logging

logger = logging.getLogger(__name__)


def parse_url_info(url):
    """
    Args:
    Returns:
    """
    url_parsed = urlsplit(url)
    query = url_parsed.query
    path = url_parsed.path
    params = parse_qs(query)
    return path, params['skuId'][0], params


def drop_duplicate_product_urls(brand_data: pd.DataFrame):
    """
    """
    brand_data = pd.json_normalize(brand_data)
    brand_data = brand_data.explode('products')
    brand_data = brand_data.reset_index()
    brand_data = brand_data[brand_data['products'].notnull()]
    brand_data['url_path'], brand_data['sku'], brand_data['url_params'] = brand_data['products'].apply(parse_url_info).str
    brand_data = brand_data.drop_duplicates(subset=['name','link','url_path', 'sku'], keep='last')
    return brand_data
    

def scroll_webpage(driver, y_height, scroll_amt=1000):
    new_height = y_height+scroll_amt
    driver.execute_script("window.scrollTo(0, "+str(new_height)+");")
    time.sleep(SCROLL_PAUSE_TIME)
    return new_height


def get_lazy_products_on_grid(driver):
    lazy_products = driver.find_elements_by_xpath('//a[@data-comp="LazyLoad ProductTile "]')
    return [prod.get_attribute('href') for prod in lazy_products]
    

def get_brand_products(url):
    """
    Brand pages display products in a grid. Products past initial load of data are loaded by scrolling down the page.
    Once "show more" button is found, click to load more products in page. Product links are added to a set. 
    TO DO -> product URLS can be parsed here to remove duplicate products 
    """
    brand_info = {}
    product_urls = []
    with webdriver.Chrome(options=options, executable_path=DRIVER_PATH) as driver:
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        try:
            expected_n_products = soup.find("p", attrs={'data-at':'number_of_products'}).getText()
            print(f'Brand has {expected_n_products} products.')
        except Exception as e:
            logger.error(f"An error occurred: {e}")

        #https://stackoverflow.com/questions/20986631/how-can-i-scroll-a-web-page-using-selenium-webdriver-in-python
        # Initially tried to scroll to bottom of page but this did not load products.
        # at top of webpage
        y_height=0
        # initial products on grid when page is opened
        products_on_load = soup.find_all('a', attrs={'data-comp':"ProductTile "}, href=True)
        product_urls.extend([prod['href'].split(" ")[0] for prod in products_on_load])
        # while there is still page left to scroll and "see more" buttons to click
        while True:
            product_urls.extend(get_lazy_products_on_grid(driver))
            
            y_height = scroll_webpage(driver, y_height)
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height<y_height:
                try:
                    # End of page if 'show more' button exists
                    driver.find_element(By.XPATH, "//button[@class='css-bk5oor eanm77i0']").click()
                except Exception as e:
                    print(f"An error occurred: {e}")
                    # End of page
                    product_urls.extend(get_lazy_products_on_grid(driver))
                    break
        driver.quit()

    parsed_urls = {}
    for url in set(product_urls):
        parsed_url = parse_url_info(url)
        #"sku:url"
        if parsed_url[0] not in parsed_urls.values():
            parsed_urls[parsed_url[1]] = parsed_url[0]
    
    print('Found '+ str(len(parsed_urls)))

    return parsed_urls


def get_sku(soup) -> str:
    """
    Returns sku code from product page in format 'Item #######'
    SKU can also be found in product URL 
    """
    try:
        sku_element = soup.find('p', attrs={'data-at': 'item-sku'})
        if sku_element is not None:
            return sku_element.text
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    
    return "No SKU Found"


def get_breadcrumb_categories(soup) -> List:
    """
    Returns list of categorical values used to describe product in header of product page
        for ex. ['Skincare','Moisturizer',...] at time of web scraping there are max of three levels in breadcrumbs
    """
    try:
        return [x.text for x in soup.find('nav', attrs={'data-comp':"ProductBreadCrumbs BreadCrumbs BreadCrumbs "}).findAll('li')]
    except Exception as e:
        logger.error(f"An error occurred: {e}")

        

def get_brand_name(soup) -> str:
    """
    Returns product brand name from product page
    """
    try:
        a_tag = soup.find("a", attrs={'data-at':"brand_name"})
        if a_tag is not None:
            return a_tag.text
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return "Unknown Brand"

       
def get_product_name(soup) -> str:
    """
    Returns product name as written on product page
    """
    try:
        span_tag = soup.find("span", attrs={'data-at': "product_name"})
        if span_tag is not None:
            return span_tag.text
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return "Unknown Product Name"


def get_num_loves(soup) -> str:
    """
    Returns number of 'love' votes for product
        loves seem to be used to track product frequently repurchased
    """
    try:
        span_tag = soup.find("div", attrs={"data-comp": "LovesCount "}).span
        if span_tag is not None:
            return span_tag.text
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return "Unknown Loves Count"


def get_product_flag_label(driver) -> str:
    try:
        flag_label = driver.find_element(By.XPATH, "//span[@data-at='product_flag_label']")
        return flag_label.text
    except Exception as e:
        logger.error(f"An error occurred: {e}")



def get_ingredients(soup) -> str:
    """
    Returns full ingredient list as a blob of text
    """
    try:
        div_ig = soup.find("div", {"id": "ingredients"})
        if div_ig is not None:
            return div_ig.text
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return "Unknown Ingredients"


def get_rating_data(soup) -> Tuple[str, str]:
    """
        Sephora product page displays a 1-5 bar histogram of votes but it is difficult to retrieve the histogram data
        ******might be able to figure this out later
        Returns star rating and number of reviews as tuple
    """
    try:
        rr_container = soup.find("a", {"href": "#ratings-reviews-container"})
        if rr_container is not None:
            star_rating = rr_container.find('span', attrs={'data-at': 'star_rating_style'})['style']
            num_reviews = rr_container.text
            return star_rating, num_reviews
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return "", ""
    

def get_product_buttons(driver, click_delay=CLICK_DELAY) -> Dict:
    """
    Products can have size and colour variations on product pages. Each product option available must be clicked
    on product page to update price.
    The data produced by this function are messy because product volume formats can look very different depending on brand.
    Additionally, this function needs to be improved to capture both original and sale prices if a product is on sale.

    """
    product_options = []
    # swatch group shows product options within category
    for swatch_grp in driver.find_elements(By.XPATH, "//div[@data-comp='SwatchGroup ']"):
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
            product_info["flag_label"] = get_product_flag_label(driver)
            try:
                product_info['size'] = driver.find_element(By.XPATH, "//span[@data-at='sku_size_label']").text
            except Exception as e:
                print(f"An error occurred: {e}")
                product_info['size'] = None
            try:
                product_info['name'] = [x.text for x in driver.find_elements_by_xpath("//div[@data-at='sku_name_label']//span")]
            except Exception as e:
                print(f"An error occurred: {e}")
                product_info['name'] = None
            # if item is on sale, there will be two b tags, first is sale, second is original price
            product_info['price'] = [b.text for b in driver.find_elements(By.XPATH, "//p[@data-comp='Price ']//b")]
            product_info['sku'] = driver.find_element(By.XPATH, "//p[@data-at='item_sku']").text
            product_options.append(product_info)
    return product_options


def get_product_page(product_url):
    """
    need to update this go just take single product url
    need to add wrapper function
    """
    url = BASE_URL+product_url
    print(url)
    time.sleep(CRAWL_DELAY)
    product = {}
    product["url"] = url
    product["error"] = ""
    product['scrape_timestamp'] = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    # get class names of buttons and grab prices with selenium 
    driver = webdriver.Chrome(options=options, executable_path=DRIVER_PATH)
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    # get_rating_histogram(driver)
    try:
        h1 = soup.find('h1').text
    except Exception as e:
        print(f"An error occurred: {e}")
        driver.quit()
        product["error"] = e
        return product
    if h1 != 'Sorry, this product is not available.' and h1!='Sorry! The page you’re looking for cannot be found.':
        product["product_name"] = get_product_name(soup)
        product["brand_name"] = get_brand_name(soup)
        product["options"] = get_product_buttons(driver)
        product["rating"], product["product_reviews"] = get_rating_data(soup)
        product["ingredients"] = get_ingredients(soup)
        product["n_loves"] = get_num_loves(soup)
        product["categories"] = get_breadcrumb_categories(soup)
    else:
        product['error'] = "Product not available"
    driver.quit()
    return product 


def get_brand_list(url):
    """ collecting brand names and links from brand list page
    url -> "https://www.sephora.com/ca/en/brands-list"
    Args:
    Returns:
    """
    brand_data = []
    with webdriver.Chrome(options=options, executable_path=DRIVER_PATH) as driver:
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()
        for brand_link in soup.findAll('a', attrs={"data-at": "brand_link"}):
            brand = {}
            brand['name'] = brand_link.span.text
            brand['link'] = brand_link.get('href') 
            brand_data.append(brand)
    return brand_data


def main():
    start_time = time.time()
    brands = get_brand_list('https://www.sephora.com/ca/en/brands-list')
    url = 'https://www.sephora.com/ca/en/brand/tower-28'
    for brand in brands:
        brand['products'] = get_brand_products(url)#get_brand_products(BASE_URL+brand['link'])
        brand['n_products'] = len(brand['products'])
        brand['scrape_timestamp'] = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        brand_products = []
        print(brand)
        for url in brand['products'].values():
            product_data = get_product_page(url)
            brand_products.append(product_data)
        print(brand_products)
        break
    print("--- %s seconds ---" % (time.time() - start_time))
    # fname = '../data/products_format_v2/'+"tower-28".replace("/","")+".json"
    # print("Saving ", fname)
    # with open(fname, "w") as outfile:
    #     outfile.write(json.dumps(brand_products, indent=4))
    

if __name__ == "__main__":
    main()