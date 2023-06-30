from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from urllib.parse import urlsplit, parse_qs
import pandas as pd

BASE_URL = 'https://www.sephora.com'
CRAWL_DELAY=5
SCROLL_PAUSE_TIME = 0.5
DRIVER_PATH = '../../chromedriver_mac64/chromedriver'
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


def get_brand_list(url):
    """ collecting brand names and links from brand list page
    url -> "https://www.sephora.com/ca/en/brands-list"
    Args:
    Returns:
    """
    driver = webdriver.Chrome(options=options, executable_path=DRIVER_PATH)
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()
    brand_data = []
    for brand_link in soup.findAll('a', attrs={"data-at": "brand_link"}):
        brand = {}
        brand['name'] = brand_link.span.text
        brand['link'] = brand_link.get('href') 
        brand_data.append(brand)
    return brand_data


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
    

def get_brand_products(url):
    """
    """
    product_urls = []
    driver = webdriver.Chrome(options=options, executable_path=DRIVER_PATH)
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    #https://stackoverflow.com/questions/20986631/how-can-i-scroll-a-web-page-using-selenium-webdriver-in-python
    # at top of webpage
    y_height=0
    expected_products = soup.find("p", attrs={'data-at':'number_of_products'}).getText()
    
    # initial products on grid when page is opened
    products_on_load = soup.find_all('a', attrs={'data-comp':"ProductTile "}, href=True)
    product_urls.extend([prod['href'].split(" ")[0] for prod in products_on_load])
    
    # last_height = driver.execute_script("return document.body.scrollHeight")
    # while there is still page left to scroll and "see more" buttons to click
    while True:
        lazy_products = driver.find_elements_by_xpath('//a[@data-comp="LazyLoad ProductTile "]')
        product_urls.extend([prod.get_attribute('href') for prod in lazy_products])
        
        driver.execute_script("window.scrollTo(0, "+str(y)+");")
        y+=1000
        time.sleep(SCROLL_PAUSE_TIME)
        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height<y:
            try:
                # End of page if 'show more' button exists
                driver.find_element(By.XPATH, "//button[@class='css-bk5oor eanm77i0']").click()
            except:
                # End of page
                lazy_products = driver.find_elements_by_xpath('//a[@data-comp="LazyLoad ProductTile "]')
                product_urls.extend([prod.get_attribute('href') for prod in lazy_products])
                break
    driver.quit()
    return list(set(product_urls))