import os
import time
import requests
import regex as re
from bs4 import BeautifulSoup

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- CONFIGURATION ---
OUTPUT_FILE = "santali_wordlist.txt"
# Ol Chiki Unicode Block: U+1C50 to U+1C7F
OL_CHIKI_PATTERN = re.compile(r'[\u1C50-\u1C7F]+')

class SantaliBot:
    def __init__(self):
        self.collected_words = set()
        self.load_existing_words()
        self.setup_driver()

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        try:
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        except Exception as e:
            print(f"Driver setup failed: {e}")
            self.driver = None

    def load_existing_words(self):
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                self.collected_words = set(line.strip() for line in f if line.strip())
            print(f"Total existing words: {len(self.collected_words)}")

    def extract_and_add(self, text):
        """Finds all Ol Chiki words in a string and adds to set."""
        if not text:
            return
        words = OL_CHIKI_PATTERN.findall(text)
        count = 0
        for w in words:
            if len(w) > 1: # Ignore single characters/noise
                if w not in self.collected_words:
                    self.collected_words.add(w)
                    count += 1
        if count > 0:
            print(f"--- Found {count} new Ol Chiki words!")

    def scrape_wiki_api(self, site_url, search_query):
        """Scrapes MediaWiki (Wikipedia/Wiktionary) using their API."""
        print(f"Searching {site_url} for '{search_query}'...")
        api_url = f"{site_url}/w/api.php"
        
        # 1. Get list of pages
        params = {
            "action": "query", "list": "search", "srsearch": search_query,
            "format": "json", "srlimit": 50
        }
        try:
            r = requests.get(api_url, params=params, timeout=10)
            pages = r.json().get("query", {}).get("search", [])
            
            for p in pages:
                # 2. Get plain text content of each page
                p_params = {
                    "action": "query", "prop": "extracts", "explaintext": True,
                    "pageids": p["pageid"], "format": "json"
                }
                pr = requests.get(api_url, params=p_params, timeout=10)
                page_data = pr.json().get("query", {}).get("pages", {})
                for pid in page_data:
                    content = page_data[pid].get("extract", "")
                    self.extract_and_add(content)
        except Exception as e:
            print(f"Wiki error: {e}")

    def scrape_url_with_selenium(self, url):
        """Scrapes dynamic sites like Reddit/Quora."""
        if not self.driver: return
        print(f"Visiting {url}...")
        try:
            self.driver.get(url)
            time.sleep(5) # Wait for JS to load
            body = self.driver.find_element(By.TAG_NAME, "body").text
            self.extract_and_add(body)
        except Exception as e:
            print(f"Selenium error at {url}: {e}")

    def save_all(self):
        # Sort words alphabetically for a clean list
        sorted_list = sorted(list(self.collected_words))
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted_list))
        print(f"Done! Final list size: {len(self.collected_words)} words.")

if __name__ == "__main__":
    bot = SantaliBot()

    # --- SOURCES ---
    # 1. Santali Wikipedia (The best source)
    # Searching for 'Santali' written in Ol Chiki: ᱥᱟᱱᱛᱟᱲᱤ
    bot.scrape_wiki_api("https://sat.wikipedia.org", "ᱥᱟᱱᱛᱟᱲᱤ")
    bot.scrape_wiki_api("https://sat.wikipedia.org", "ᱥᱟᱱᱛᱟᱲ")
    
    # 2. English Wiktionary (Scrape Santali section)
    bot.scrape_wiki_api("https://en.wiktionary.org", "Santali")

    # 3. Web Pages / Social Media
    web_targets = [
        "https://sat.wikipedia.org/wiki/ᱢᱩᱬᱩᱛ_ᱥᱟᱦᱴᱟ", # Main Page
        "https://www.reddit.com/r/Santali/",
        "https://www.facebook.com/public/Santali-Ol-Chiki", # Note: Limited success without login
    ]
    for url in web_targets:
        bot.scrape_url_with_selenium(url)

    bot.save_all()
    if bot.driver:
        bot.driver.quit()
