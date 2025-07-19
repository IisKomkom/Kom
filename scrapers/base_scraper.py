import requests
import time
import logging
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
import cloudscraper
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Optional
import re
from config import SCRAPING_CONFIG

class BaseScraper:
    def __init__(self, site_name: str, base_url: str, selectors: Dict[str, str]):
        self.site_name = site_name
        self.base_url = base_url
        self.selectors = selectors
        self.logger = logging.getLogger(f"{__name__}.{site_name}")
        self.session = requests.Session()
        self.driver = None
        self.ua = UserAgent()
        self.setup_session()
        
    def setup_session(self):
        """Setup requests session with headers and user agent rotation"""
        self.session.headers.update(SCRAPING_CONFIG['headers'])
        self.session.headers['User-Agent'] = random.choice(SCRAPING_CONFIG['user_agents'])
        
        # Setup cloudscraper for Cloudflare bypass
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
    def setup_selenium(self, headless: bool = True):
        """Setup Selenium WebDriver"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(f"--user-agent={self.ua.random}")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Disable images for faster loading
            prefs = {"profile.managed_default_content_settings.images": 2}
            chrome_options.add_experimental_option("prefs", prefs)
            
            self.driver = webdriver.Chrome(
                ChromeDriverManager().install(),
                options=chrome_options
            )
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info("Selenium WebDriver initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to setup Selenium: {e}")
            
    def get_page(self, url: str, use_selenium: bool = False, retries: int = 3) -> Optional[BeautifulSoup]:
        """Get page content with retry logic"""
        for attempt in range(retries):
            try:
                if use_selenium:
                    return self._get_page_selenium(url)
                else:
                    return self._get_page_requests(url)
                    
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(random.uniform(2, 5))
                else:
                    self.logger.error(f"All attempts failed for {url}")
                    
        return None
    
    def _get_page_requests(self, url: str) -> Optional[BeautifulSoup]:
        """Get page using requests/cloudscraper"""
        # Try cloudscraper first (for Cloudflare bypass)
        try:
            response = self.scraper.get(url, timeout=SCRAPING_CONFIG['timeout'])
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except:
            pass
            
        # Fallback to regular requests
        try:
            response = self.session.get(url, timeout=SCRAPING_CONFIG['timeout'])
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            self.logger.error(f"Requests failed for {url}: {e}")
            raise
    
    def _get_page_selenium(self, url: str) -> Optional[BeautifulSoup]:
        """Get page using Selenium"""
        if not self.driver:
            self.setup_selenium()
            
        try:
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Random delay to mimic human behavior
            time.sleep(random.uniform(1, 3))
            
            return BeautifulSoup(self.driver.page_source, 'html.parser')
            
        except TimeoutException:
            self.logger.error(f"Timeout loading page: {url}")
            raise
        except WebDriverException as e:
            self.logger.error(f"WebDriver error: {e}")
            raise
    
    def extract_text(self, soup: BeautifulSoup, selector: str, default: str = "") -> str:
        """Extract text using CSS selector"""
        try:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
            return default
        except Exception as e:
            self.logger.warning(f"Failed to extract text with selector '{selector}': {e}")
            return default
    
    def extract_links(self, soup: BeautifulSoup, selector: str) -> List[str]:
        """Extract links using CSS selector"""
        try:
            elements = soup.select(selector)
            links = []
            for element in elements:
                href = element.get('href')
                if href:
                    full_url = urljoin(self.base_url, href)
                    links.append(full_url)
            return links
        except Exception as e:
            self.logger.warning(f"Failed to extract links with selector '{selector}': {e}")
            return []
    
    def extract_download_links(self, soup: BeautifulSoup, item_url: str = None) -> List[str]:
        """Extract download links from page"""
        download_links = []
        
        # Try multiple selectors for download links
        download_selectors = [
            self.selectors.get('download_link', ''),
            'a[href*="download"]',
            'a[href*="mirror"]',
            'a[href*="link"]',
            'a.download',
            'a.btn-download',
            '.download-button a',
            '.download-link a'
        ]
        
        for selector in download_selectors:
            if not selector:
                continue
                
            links = self.extract_links(soup, selector)
            download_links.extend(links)
        
        # Remove duplicates and filter
        download_links = list(set(download_links))
        download_links = self.filter_download_links(download_links)
        
        # If no direct download links found, try to follow redirect pages
        if not download_links and item_url:
            download_links = self.resolve_redirect_links(soup, item_url)
        
        return download_links
    
    def filter_download_links(self, links: List[str]) -> List[str]:
        """Filter and validate download links"""
        valid_links = []
        
        for link in links:
            # Skip obviously invalid links
            if any(skip in link.lower() for skip in ['javascript:', 'mailto:', '#', 'void(0)']):
                continue
                
            # Skip social media and irrelevant links
            if any(skip in link.lower() for skip in ['facebook', 'twitter', 'instagram', 'youtube', 'telegram']):
                continue
                
            # Prefer direct file links
            if any(ext in link.lower() for ext in ['.exe', '.msi', '.dmg', '.app', '.apk', '.zip', '.rar', '.7z']):
                valid_links.insert(0, link)  # Prioritize direct file links
            else:
                valid_links.append(link)
        
        return valid_links
    
    def resolve_redirect_links(self, soup: BeautifulSoup, item_url: str) -> List[str]:
        """Resolve download links from redirect pages"""
        download_links = []
        
        # Look for common redirect patterns
        redirect_selectors = [
            'a[href*="go.php"]',
            'a[href*="redirect"]',
            'a[href*="out.php"]',
            'a[href*="link.php"]'
        ]
        
        for selector in redirect_selectors:
            redirect_links = self.extract_links(soup, selector)
            
            for redirect_link in redirect_links[:3]:  # Limit to avoid too many requests
                try:
                    final_url = self.follow_redirects(redirect_link)
                    if final_url and self.is_direct_download_link(final_url):
                        download_links.append(final_url)
                except Exception as e:
                    self.logger.warning(f"Failed to resolve redirect {redirect_link}: {e}")
        
        return download_links
    
    def follow_redirects(self, url: str, max_redirects: int = 5) -> Optional[str]:
        """Follow redirects to get final URL"""
        try:
            response = self.session.head(url, allow_redirects=True, timeout=10)
            
            # Check if it's a direct download link
            content_type = response.headers.get('content-type', '').lower()
            if any(t in content_type for t in ['application/', 'binary/']):
                return response.url
                
            # Check file extension in URL
            if any(ext in response.url.lower() for ext in ['.exe', '.msi', '.dmg', '.app', '.apk', '.zip', '.rar', '.7z']):
                return response.url
                
        except Exception as e:
            self.logger.warning(f"Failed to follow redirects for {url}: {e}")
            
        return None
    
    def is_direct_download_link(self, url: str) -> bool:
        """Check if URL is a direct download link"""
        try:
            response = self.session.head(url, timeout=10)
            content_type = response.headers.get('content-type', '').lower()
            
            # Check content type
            if any(t in content_type for t in ['application/', 'binary/']):
                return True
                
            # Check file extension
            if any(ext in url.lower() for ext in ['.exe', '.msi', '.dmg', '.app', '.apk', '.zip', '.rar', '.7z']):
                return True
                
        except:
            pass
            
        return False
    
    def extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract additional metadata from page"""
        metadata = {}
        
        # Extract common metadata
        metadata_selectors = {
            'author': ['[name="author"]', '.author', '.developer'],
            'publisher': ['[name="publisher"]', '.publisher', '.company'],
            'release_date': ['[name="date"]', '.date', '.release-date'],
            'rating': ['.rating', '.score', '.stars'],
            'language': ['.language', '.lang'],
            'platform': ['.platform', '.os', '.system'],
            'license': ['.license', '.licence'],
            'tags': ['.tags', '.keywords', '.categories']
        }
        
        for key, selectors in metadata_selectors.items():
            for selector in selectors:
                value = self.extract_text(soup, selector)
                if value:
                    metadata[key] = value
                    break
        
        # Extract meta tags
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name', '').lower()
            content = tag.get('content', '')
            
            if name in ['description', 'keywords', 'author'] and content:
                metadata[name] = content
        
        return metadata
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
            
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common unwanted characters
        text = re.sub(r'[^\w\s\-\.\(\)\[\]\/]', '', text)
        
        return text.strip()
    
    def extract_file_size(self, text: str) -> Optional[str]:
        """Extract file size from text"""
        size_pattern = r'(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB|B)'
        match = re.search(size_pattern, text, re.IGNORECASE)
        
        if match:
            return f"{match.group(1)} {match.group(2).upper()}"
        
        return None
    
    def extract_version(self, text: str) -> Optional[str]:
        """Extract version number from text"""
        version_patterns = [
            r'v?(\d+(?:\.\d+){1,3}(?:\.\d+)?)',
            r'version\s*:?\s*(\d+(?:\.\d+){1,3})',
            r'ver\.\s*(\d+(?:\.\d+){1,3})'
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def delay(self):
        """Add random delay between requests"""
        delay_time = random.uniform(
            SCRAPING_CONFIG['delay_between_requests'],
            SCRAPING_CONFIG['delay_between_requests'] * 2
        )
        time.sleep(delay_time)
    
    def close(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        
        if self.session:
            try:
                self.session.close()
            except:
                pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()