from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
import pickle
import time

# CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
SCREENER_LOGIN_URL = "https://www.screener.in/login?"
SCREENER_USERNAME = "deepan.antony@gmail.com"
SCREENER_PASSWORD = "Ansible!234"

class SeleniumSession:
    def __init__(self):
        self.browser = self.start_browser()
        self.login()

    def start_browser(self):
        """Initialize a persistent Selenium browser session."""
        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/google-chrome"
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_service = ChromeService(CHROMEDRIVER_PATH)

        return webdriver.Chrome(service=chrome_service, options=chrome_options)

    def login(self):
        """Logs in to Screener and saves session cookies."""
        self.browser.get(SCREENER_LOGIN_URL)
        try:
            self.browser.find_element("name", "username").send_keys(SCREENER_USERNAME)
            self.browser.find_element("name", "password").send_keys(SCREENER_PASSWORD)
            self.browser.find_element("css selector", "button[type='submit']").click()
            time.sleep(5)  # Ensure login completes
            pickle.dump(self.browser.get_cookies(), open("cookies.pkl", "wb"))
        except Exception as e:
            print(f"Login failed: {e}")

    def get_browser(self):
        """Returns the current Selenium browser session."""
        return self.browser

    def quit(self):
        """Closes the browser session."""
        self.browser.quit()

# Initialize persistent session
selenium_session = SeleniumSession()
