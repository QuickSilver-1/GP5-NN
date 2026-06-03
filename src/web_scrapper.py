from selenium import webdriver
from regex import D
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote import webelement
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
import time
import src.config as config
from src.excel_handler import ExcelHandler, DataSetType
from structlog import BoundLogger
from selenium_stealth import stealth
import random
import re
import pandas as pd

class SeleniumScraper:
    logger: BoundLogger
    cfg: config.HouseScrapper
    excel_handler: ExcelHandler
        
    def __init__(self, cfg: config.HouseScrapper, logger: BoundLogger, excel_handler: ExcelHandler, chrome_port: int):
        self.cfg = cfg
        
        self.chrome_option = Options()
        self.chrome_option.add_argument("--disable-blink-features=AutomationControlled")
        # self.chrome_option.add_experimental_option("excludeSwitches", ["enable-automation"])
        # self.chrome_option.add_experimental_option('useAutomationExtension', False)
        self.chrome_option.add_argument("user-agent=" + cfg.user_agent)
        self.chrome_option.add_argument("--window-size=1920,1080")
        self.chrome_option.add_argument(f'--user-data-dir=C:\\temp\\chrome_debug_profile_{chrome_port}')
        self.chrome_option.add_experimental_option("debuggerAddress", "127.0.0.1:" + str(chrome_port))

        # self.options = {
        #     'disable_encoding': True,
        #     'verify_ssl': False,
        #     'args': ['--log-level=3', '--silent'],
        #     'excludeSwitches': ['enable-logging']
        # }

        self.excel_handler = excel_handler
        self.df = self.excel_handler.get_df(DataSetType.RAW)
        
        self.driver = webdriver.Chrome(
            options=self.chrome_option,
        )        

        self.logger = logger.bind(service="SeleniumScraper")
        self.logger.info("SeleniumScraper initialized with user agent: %s", cfg.user_agent)
        
    def scrape(self, query):
        logger = self.logger.bind(method="scrape")
        logger.info("Starting scraping...")
        
        logger.info("Configuring stealth settings...")
        stealth(
            self.driver,
            languages=["ru"],
            vendor="Google Inc.",
            platform="Win64",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

        # self.excel_handler.clear(DataSetType.RAW)
        # self.logger.info("Excel file cleared, starting to scrape data...")

        try:
            self.driver.get(self.cfg.domain)
            time.sleep(1 + random.random())
            # WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CSS_SELECTOR, "button[data-e2e-id='cookie-alert-accept']"))

            # button = WebDriverWait(driver, 10).until(
            #    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-e2e-id='cookie-alert-accept']"))
            # )
            # button.click()

            # time.sleep(2 + random.random())
            # button = WebDriverWait(driver, 10).until(
            #     EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Да, верно']]"))
            # )
            # button.click()
            
            search = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Город, ЖК, адрес, метро, район']"))
            )

            self.__move_mouse_smoothly(search)
            search.send_keys(Keys.CONTROL + "a")
            search.send_keys(Keys.BACK_SPACE)
            search.send_keys(query)
            time.sleep(15)
            
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-e2e-id='main-search-button']"))
            )
            button.click()
            time.sleep(random.uniform(0.2, 0.5))
            
        except Exception as e:
            self.logger.error("failed to antibot passing: %s", e)
            return
        
        main_tab = self.driver.current_window_handle
        offset = 0
        countList = 1
        countCards = 1
        while True:
            try:
                if countList > 50:
                    cards = self.driver.find_elements(By.CSS_SELECTOR, "a.sQ7Tu")[offset:]
                    offset = len(cards)
                    for i in range(len(cards)):
                        WebDriverWait(self.driver, 1).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.sQ7Tu"))
                        )
                        time.sleep(1)
                        card = cards[i]
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                        time.sleep(random.uniform(0.1, 0.3))
                        
                        self.__move_mouse_smoothly(card)
                        for handle in self.driver.window_handles:
                            if handle != main_tab:
                                self.driver.switch_to.window(handle)
                                
                        time.sleep(random.uniform(0.2, 0.5))
                        
                        self.logger.info("Scraping card %d with url: %s", countCards, self.driver.current_url)
                        self.__save_card_params(countCards%20 == 0)
                        countCards += 1

                        for handle in self.driver.window_handles:
                            if handle != main_tab:
                                self.driver.switch_to.window(handle)
                                self.driver.close()
                        
                        self.driver.switch_to.window(main_tab)
                    
                else:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                    
                if countList%2 == 0:
                    button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-e2e-id='next-offers-button']"))
                    )
                    
                    button.click()
                    time.sleep(random.uniform(0.5, 1))
        
                countList += 1
            except Exception as e:
                self.logger.error("failed to parse data: %s", e)
                continue
            
        # except Exception as e:
        #     self.logger.error("failed to scrape: %s", e)
        
        # finally:
        #     self.logger.info("Scraping finished, scrape %d cards", len(self.df))
        #     self.excel_handler.save(DataSetType.RAW, self.df)
        
        self.driver.quit()
        # for request in self.driver.requests:
        #     self.logger.debug(f"🔗 {request.method} {request.url}")
            
        #     self.logger.debug("ЗАГОЛОВКИ ЗАПРОСА:")
        #     for name, value in request.headers.items():
        #         self.logger.debug(f"{name}: {value}")

        #     if request.body:
        #         self.logger.debug(f"ТЕЛО ЗАПРОСА: {request.body[:500]}")

    def __move_mouse_smoothly(self, element: webelement.WebElement) -> None:
        actions = ActionChains(self.driver)
        
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(random.uniform(0.1, 0.2))
        
        actions.move_to_element(element)
        actions.pause(random.uniform(0.1, 0.3))
        actions.click()
        actions.perform()
        
    def __save_card_params(self, is_save: bool) -> None:
        params = {}
        try:
            self.logger.info("attemp 1 to save card params")

            # Проверка на 1 или 2 флоу (первичка или вторичка)
            float_params = WebDriverWait(self.driver, 1).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "C_L_4"))
            )

            try:
                button = WebDriverWait(self.driver, 1).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "UywXz"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                button.find_element(By.TAG_NAME, "button").click()
                time.sleep(random.uniform(0.2, 0.5))
                
            except Exception as e:
                self.logger.error("failed to find button to show params: %s", e)
            
            try:
                address = WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-e2e-id='building_uri']"))
                )
                params["Адрес"] = address.text
            except Exception as e:
                self.logger.error("failed to extract address: %s", e)
                params["Адрес"] = ""
                return
            
            try:
                float_params = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "C_L_4"))
                )
            except Exception as e:
                self.logger.error("failed to find float params: %s", e)
                float_params = []
                
            for float_param in float_params:
                try:
                    name = float_param.get_attribute("data-e2e-id")
                    value = float_param.find_element(By.CLASS_NAME, "yNtG9").text
                    params[name] = value
                except Exception as e:
                    self.logger.error("failed to extract float param: %s", e)

            try:
                description_button = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "JDk06"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", description_button)
                description_button.click()
                time.sleep(random.uniform(0.2, 0.5))
                
                description = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.ID, "description"))
                )            
                params["Описание"] = description.text.replace("Скрыть", "").strip()
                
            except Exception as e:
                self.logger.error("failed to find button to show description: %s", e)
                
            try:
                description = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.ID, "description"))
                )            
                params["Описание"] = description.text.replace("Скрыть", "").strip()
                
            except Exception as e:
                self.logger.error("failed to find button to show description: %s", e)
            
            try:
                house_params = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "ByFq7"))
                )
            except Exception as e:
                self.logger.error("failed to find house params: %s", e)
                house_params = []
                
            for house_param in house_params:
                try:
                    name = house_param.get_attribute("data-e2e-id")
                    value = house_param.find_element(By.CLASS_NAME, "upbHP").text
                    params[name] = value
                except Exception as e:
                    self.logger.error("failed to extract house param: %s", e)
                
            try:
                metro = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "OQfZ9"))
                )[0]
            
                try:
                    metro_name = metro.find_element(By.CSS_SELECTOR, "a.vUk21").text
                except Exception as e:
                    self.logger.info("failed to get metro name: %s", e)
                    metro_name = metro.find_element(By.CSS_SELECTOR, "span.vUk21").text
                
                metro_time = metro.find_element(By.CLASS_NAME, "_nDux").text
                params["Метро"] = metro_name
                params["Время до метро"] = int(re.sub(r"\D", "", metro_time)) if metro_time else 0
            except Exception as e:
                self.logger.error("failed to extract metro info: %s", e)
            
            try:
                price = self.driver.find_elements(By.CLASS_NAME, "JfVCK")[1].find_element(By.TAG_NAME, "span").text
                params["Цена"] = int(re.sub(r"\D", "", price)) if price else 0
            
            except Exception as e:
                self.logger.error("failed to extract price: %s", e)
                
        except TimeoutException as e:
            self.logger.info("attemp 2 to save card params")
            
            try:
                button = WebDriverWait(self.driver, 1).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "bawL3"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                button.find_element(By.TAG_NAME, "button").click()
                time.sleep(random.uniform(0.2, 0.5))
                
            except Exception as e:
                self.logger.error("failed to click button to show params: %s", e)
            
            try:            
                address = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "a4fZk"))
                )
                params["Адрес"] = address.text
            except Exception as e:
                self.logger.error("failed to extract address: %s", e)
                params["Адрес"] = ""
                return
                        
            try:
                float_params = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "tau7O"))
                )
            except Exception as e:
                self.logger.error("failed to find float params: %s", e)
                float_params = []
                
            for float_param in float_params:
                try:
                    name = float_param.find_element(By.CLASS_NAME, "K_m3c").text
                    value = float_param.find_element(By.CLASS_NAME, "BCmK9").text
                    params[name] = value
                except Exception as e:
                    self.logger.error("failed to extract float param: %s", e)
                
            try:
                description_button = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "p0G1l"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", description_button)
                description_button.click()
                time.sleep(random.uniform(0.2, 0.5))

            except Exception as e:
                self.logger.error("failed to extract description: %s", e)
                
            try:
                description = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "qkifF"))
                )            
                params["Описание"] = description.find_element(By.TAG_NAME, "p").text
            
            except Exception as e:
                self.logger.error("failed to extract description: %s", e)
            
            try:
                house_params = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "nJDVt"))
                )
            except Exception as e:
                self.logger.error("failed to find house params: %s", e)
                house_params = []
                
            for house_param in house_params:
                try:
                    spans = house_param.find_elements(By.CSS_SELECTOR, ".Qgi72 span")
                    name = ""
                    for span in spans:
                        name += span.text.strip()
                    
                    name = name.replace("\xa0", " ").strip()
                    value = house_param.find_element(By.CLASS_NAME, "wib4o").find_element(By.TAG_NAME, "span").text
                    params[name] = value
                except Exception as e:
                    self.logger.error("failed to extract house param: %s", e)
            
            try:
                metro = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "fpnpQ"))
                )[0]
                
                metro_name = metro.find_element(By.CLASS_NAME, "txky0").text
                metro_time = metro.find_element(By.CLASS_NAME, "MdOHP").text
                params["Метро"] = metro_name
                params["Время до метро"] = int(re.sub(r"\D", "", metro_time)) if metro_time else 0
            except Exception as e:
                self.logger.error("failed to extract metro info: %s", e)
            try:
                price = self.driver.find_element(By.CLASS_NAME, "vAU5N").text
                params["Цена"] = int(re.sub(r"\D", "", price)) if price else 0
            except Exception as e:
                self.logger.error("failed to extract price: %s", e)
            
        existing_pairs = set(zip(self.df['Адрес'], self.df['Площадь']))
        if (params['Адрес'], params['Площадь']) not in existing_pairs:
            self.df = pd.concat([self.df, pd.DataFrame([params])], ignore_index=True)
        else:
            self.logger.error("card already in dataset")
            
        if is_save:
            self.excel_handler.save(DataSetType.RAW, self.df)
