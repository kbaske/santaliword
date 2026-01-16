import os
import time
import requests
import regex as re  # Advanced regex for better Unicode support
from bs4 import BeautifulSoup

# Selenium Imports for scraping dynamic sites
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- CONFIGURATION ---
OUTPUT_FILE = "santali_wordlist.txt"

# Standard User-Agent to avoid getting blocked immediately
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Ol Chiki Unicode Block: U+1C50 to U+1C7F
# We look for words that contain at least one character from this block.
OL_CHIKI_PATTERN = re.compile(r'[\u1C50-\u1C7F]+')

class SantaliBot:
    def __init__(self):
        self.collected_words = set()
        self.load_existing_words()
        self.setup_driver()

    def setup_driver(self):
        """Sets up the Headless Chrome Browser."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run without GUI
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage") # Vital for GitHub Actions
        chrome_options.add_argument(f"user-agent={USER_AGENT}")

        # Automatically installs the correct driver version for the system
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=chrome_options
            )
            print("Browser driver setup successful.")
        except Exception as e:
            print(f"Failed to setup browser driver: {e}")
            self.driver = None

    def load_existing_words(self):
        """Loads existing words from file to prevent duplicates."""
        if os.path.exists(OUTPUT_FILE):
            try:
                with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip()
                        if word:
                            self.collected_words.add(word)
                print(f"Loaded {len(self.collected_words)} existing words.")
            except Exception as e:
                print(f"Error reading file: {e}")
        else:
            print("No existing wordlist found. Creating new.")

    def save_words(self):
        """Sorts and saves the unique word list to the file."""
        try:
            sorted_words = sorted(list(self.collected_words))
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted_words))
            print(f"SUCCESS: Saved {len(self.collected_words)} unique words to {OUTPUT_FILE}.")
        except Exception as e:
            print(f"Error saving file: {e}")

    def process_text(self, text):
    if not text:
        return

    # This findall will grab EVERY sequence of Ol Chiki characters 
    # regardless of what punctuation or Latin text is around it.
    found_words = OL_CHIKI_PATTERN.findall(text)
    
    for word in found_words:
        if len(word) > 1: # Ignore single character noise
            self.collected_words.add(word)
    
    if found_words:
        print(f"Extracted {len(found_words)} Ol Chiki tokens from text.")

        # Split text into tokens by whitespace
        tokens = text.split()
        
        for token in tokens:
            # Remove common punctuation marks from edges of the word
            # We keep the core word intact
            clean_token = re.sub(r'^[^\w\u1C50-\u1C7F]+|[^\w\u1C50-\u1C7F]+$', '', token)
            
            # Check if the cleaned token contains Ol Chiki characters
            if OL_CHIKI_PATTERN.search(clean_token):
                self.collected_words.add(clean_token)

    # --- METHOD 1: API SCRAPING (Best for Wikipedia/Wiktionary) ---
    def scrape_mediawiki(self, base_url, search_term="Santali", limit=50):
        print(f"--- Scraping API: {base_url} ---")
        session = requests.Session()
        api_url = f"{base_url}/w/api.php"
        
        # Step 1: Search for pages
        search_params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": search_term,
            "srlimit": limit
        }
        
        try:
            response = session.get(url=api_url, params=search_params)
            data = response.json()
            
            page_ids = []
            if "query" in data and "search" in data["query"]:
                for item in data["query"]["search"]:
                    page_ids.append(str(item["pageid"]))
            
            print(f"Found {len(page_ids)} pages. Extracting content...")

            # Step 2: Get content for these pages (Batch processing)
            # MediaWiki allows fetching multiple pages at once
            chunk_size = 20
            for i in range(0, len(page_ids), chunk_size):
                chunk = page_ids[i:i+chunk_size]
                content_params = {
                    "action": "query",
                    "format": "json",
                    "prop": "extracts",
                    "pageids": "|".join(chunk),
                    "explaintext": True # Get plain text, not HTML
                }
                
                content_resp = session.get(url=api_url, params=content_params)
                content_data = content_resp.json()
                
                if "query" in content_data and "pages" in content_data["query"]:
                    for pid, pdata in content_data["query"]["pages"].items():
                        if "extract" in pdata:
                            self.process_text(pdata["extract"])
                            
        except Exception as e:
            print(f"Error scraping MediaWiki {base_url}: {e}")

    # --- METHOD 2: SELENIUM SCRAPING (For Reddit, Quora, etc.) ---
    def scrape_dynamic_url(self, url):
        if not self.driver:
            print("Driver not initialized. Skipping dynamic scrape.")
            return

        print(f"--- Scraping Dynamic Site: {url} ---")
        try:
            self.driver.get(url)
            time.sleep(3)  # Wait for load

            # Scroll logic to trigger lazy loading
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 4 

            while scroll_attempts < max_scrolls:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
                scroll_attempts += 1

            # Extract visible text from the body
            body_element = self.driver.find_element(By.TAG_NAME, "body")
            page_text = body_element.text
            self.process_text(page_text)

        except Exception as e:
            print(f"Error scraping {url}: {e}")

    def close(self):
        if self.driver:
            self.driver.quit()
            print("Browser closed.")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    bot = SantaliBot()

    # 1. API SOURCES (Fast & Reliable)
    # Santali Wikipedia
    bot.scrape_mediawiki("https://sat.wikipedia.org", search_term="ᱚᱞ ᱪᱤᱠᱤ", limit=300)
    # Santali Wiktionary (searching for Santali words)
    bot.scrape_mediawiki("https://sat.wiktionary.org", search_term="ᱥᱟᱱᱛᱟᱲᱤ", limit=150)
    # English Wiktionary (searching for Santali words)
    bot.scrape_mediawiki("https://en.wiktionary.org", search_term="Santali", limit=50)
    # Wikisource
    bot.scrape_mediawiki("https://sat.wikisource.org", search_term="Santali", limit=30)

    # 2. DYNAMIC SOURCES (Slower, uses Browser)
    # Add specific threads or search result URLs here
    dynamic_urls = [
        "https://www.reddit.com/r/Santali/",
        "https://www.quora.com/topic/Santali-Language",
        # Note: Facebook/Instagram require login and are very hard to scrape automatically.
        # It is better to paste text from FB manually into a file if needed.
    ]

    for url in dynamic_urls:
        bot.scrape_dynamic_url(url)

    # 3. FINISH
    bot.save_words()
    bot.close()
