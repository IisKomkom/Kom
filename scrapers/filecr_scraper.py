from scrapers.base_scraper import BaseScraper
from typing import List, Dict, Any, Optional
import re
from urllib.parse import urljoin, urlparse
import time

class FilecrScraper(BaseScraper):
    def __init__(self):
        site_config = {
            'base_url': 'https://filecr.com',
            'selectors': {
                'title': 'h1.entry-title',
                'download_link': 'a[href*="download"], .download-link a',
                'description': '.entry-content p',
                'version': '.version-info, .software-version',
                'size': '.file-size, .download-size',
                'category': '.category-links a, .post-categories a'
            }
        }
        
        super().__init__(
            site_name='filecr',
            base_url=site_config['base_url'],
            selectors=site_config['selectors']
        )
        
        self.categories = [
            '/category/windows/',
            '/category/macos/',
            '/category/android/',
            '/category/games/',
            '/category/software/',
            '/category/drivers/'
        ]
    
    def scrape_category(self, category_url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
        """Scrape all items from a category"""
        items = []
        base_category_url = urljoin(self.base_url, category_url)
        
        for page in range(1, max_pages + 1):
            page_url = f"{base_category_url}page/{page}/" if page > 1 else base_category_url
            
            self.logger.info(f"Scraping {page_url}")
            
            try:
                soup = self.get_page(page_url)
                if not soup:
                    break
                
                # Extract item links from category page
                item_links = self.extract_item_links(soup)
                
                if not item_links:
                    self.logger.info(f"No items found on page {page}, stopping")
                    break
                
                # Scrape each item
                for item_url in item_links:
                    try:
                        item_data = self.scrape_item(item_url)
                        if item_data:
                            items.append(item_data)
                    except Exception as e:
                        self.logger.error(f"Failed to scrape item {item_url}: {e}")
                    
                    self.delay()
                
                self.logger.info(f"Scraped {len(item_links)} items from page {page}")
                
            except Exception as e:
                self.logger.error(f"Failed to scrape page {page_url}: {e}")
            
            self.delay()
        
        return items
    
    def extract_item_links(self, soup) -> List[str]:
        """Extract item links from category page"""
        item_links = []
        
        # Multiple selectors for item links
        selectors = [
            'h2.entry-title a',
            '.post-title a',
            'article h2 a',
            '.entry-header h2 a',
            'h3.entry-title a'
        ]
        
        for selector in selectors:
            links = self.extract_links(soup, selector)
            item_links.extend(links)
        
        # Remove duplicates
        item_links = list(set(item_links))
        
        # Filter valid item links
        filtered_links = []
        for link in item_links:
            # Skip category, tag, and other non-item pages
            if any(skip in link for skip in ['/category/', '/tag/', '/page/', '/author/']):
                continue
            
            # Must be a post URL
            if '/20' in link or re.search(r'/\d{4}/', link):
                filtered_links.append(link)
        
        return filtered_links
    
    def scrape_item(self, item_url: str) -> Optional[Dict[str, Any]]:
        """Scrape individual item page"""
        try:
            soup = self.get_page(item_url)
            if not soup:
                return None
            
            # Extract basic information
            title = self.extract_text(soup, self.selectors['title'])
            if not title:
                # Fallback title selectors
                title = self.extract_text(soup, 'h1') or self.extract_text(soup, '.post-title')
            
            if not title:
                self.logger.warning(f"No title found for {item_url}")
                return None
            
            # Clean title
            title = self.clean_title(title)
            
            # Extract description
            description = self.extract_description(soup)
            
            # Extract version and size
            version = self.extract_version_info(soup, title)
            file_size = self.extract_size_info(soup)
            
            # Extract category
            category = self.extract_category(soup, item_url)
            
            # Extract download links
            download_links = self.extract_download_links(soup, item_url)
            
            # Extract additional metadata
            metadata = self.extract_metadata(soup)
            metadata.update({
                'scraped_from': 'filecr',
                'original_url': item_url,
                'screenshots': self.extract_screenshots(soup),
                'requirements': self.extract_requirements(soup),
                'changelog': self.extract_changelog(soup)
            })
            
            item_data = {
                'title': title,
                'url': item_url,
                'source_site': 'filecr',
                'category': category,
                'version': version,
                'file_size': file_size,
                'description': description,
                'download_links': download_links,
                'metadata': metadata
            }
            
            self.logger.info(f"Successfully scraped: {title}")
            return item_data
            
        except Exception as e:
            self.logger.error(f"Error scraping item {item_url}: {e}")
            return None
    
    def clean_title(self, title: str) -> str:
        """Clean and normalize title"""
        # Remove common suffixes
        patterns_to_remove = [
            r'\s*-\s*FileCR$',
            r'\s*\|\s*FileCR$',
            r'\s*Download.*$',
            r'\s*Free Download.*$',
            r'\s*\[.*?\]$',
            r'\s*\(.*?\)$'
        ]
        
        for pattern in patterns_to_remove:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        return self.clean_text(title)
    
    def extract_description(self, soup) -> str:
        """Extract and clean description"""
        description_parts = []
        
        # Try multiple selectors
        selectors = [
            '.entry-content p',
            '.post-content p',
            '.content p',
            'article p'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements[:3]:  # Limit to first 3 paragraphs
                text = elem.get_text(strip=True)
                if text and len(text) > 20:  # Skip very short paragraphs
                    description_parts.append(text)
        
        description = ' '.join(description_parts)
        
        # Clean description
        description = re.sub(r'\s+', ' ', description)
        description = description[:1000]  # Limit length
        
        return description
    
    def extract_version_info(self, soup, title: str) -> Optional[str]:
        """Extract version information"""
        # Try specific version selectors
        version = self.extract_text(soup, self.selectors['version'])
        
        if not version:
            # Look in title
            version = self.extract_version(title)
        
        if not version:
            # Look in content
            content_text = soup.get_text()
            version = self.extract_version(content_text)
        
        return version
    
    def extract_size_info(self, soup) -> Optional[str]:
        """Extract file size information"""
        # Try specific size selectors
        size_text = self.extract_text(soup, self.selectors['size'])
        
        if size_text:
            size = self.extract_file_size(size_text)
            if size:
                return size
        
        # Look in full content
        content_text = soup.get_text()
        return self.extract_file_size(content_text)
    
    def extract_category(self, soup, item_url: str) -> Optional[str]:
        """Extract category information"""
        # Try specific category selectors
        category = self.extract_text(soup, self.selectors['category'])
        
        if not category:
            # Extract from URL
            for cat in self.categories:
                if cat.strip('/') in item_url:
                    return cat.strip('/').split('/')[-1].title()
        
        return category
    
    def extract_screenshots(self, soup) -> List[str]:
        """Extract screenshot URLs"""
        screenshots = []
        
        # Look for images in content
        img_elements = soup.select('.entry-content img, .post-content img, .gallery img')
        
        for img in img_elements:
            src = img.get('src') or img.get('data-src')
            if src:
                # Skip small images (likely icons)
                width = img.get('width')
                height = img.get('height')
                
                if width and height:
                    try:
                        if int(width) < 200 or int(height) < 150:
                            continue
                    except:
                        pass
                
                full_url = urljoin(self.base_url, src)
                screenshots.append(full_url)
        
        return screenshots[:5]  # Limit to 5 screenshots
    
    def extract_requirements(self, soup) -> Dict[str, str]:
        """Extract system requirements"""
        requirements = {}
        
        content_text = soup.get_text().lower()
        
        # Look for common requirement patterns
        req_patterns = {
            'os': r'operating system[:\s]*([^\n\r]+)',
            'processor': r'processor[:\s]*([^\n\r]+)',
            'memory': r'memory[:\s]*([^\n\r]+)',
            'storage': r'storage[:\s]*([^\n\r]+)',
            'graphics': r'graphics[:\s]*([^\n\r]+)'
        }
        
        for req_type, pattern in req_patterns.items():
            match = re.search(pattern, content_text)
            if match:
                requirements[req_type] = match.group(1).strip()
        
        return requirements
    
    def extract_changelog(self, soup) -> str:
        """Extract changelog or what's new information"""
        changelog_selectors = [
            '.changelog',
            '.whats-new',
            '.version-info',
            '.release-notes'
        ]
        
        for selector in changelog_selectors:
            changelog = self.extract_text(soup, selector)
            if changelog:
                return changelog[:500]  # Limit length
        
        return ""
    
    def extract_download_links(self, soup, item_url: str = None) -> List[str]:
        """Extract download links specific to FileCR"""
        download_links = []
        
        # FileCR specific selectors
        filecr_selectors = [
            'a[href*="download"]',
            'a[href*="mirror"]',
            'a[href*="link"]',
            '.download-links a',
            '.download-button',
            '.btn-download'
        ]
        
        for selector in filecr_selectors:
            links = self.extract_links(soup, selector)
            download_links.extend(links)
        
        # Look for embedded download links in scripts
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Look for URLs in JavaScript
                urls = re.findall(r'https?://[^\s\'"<>]+', script.string)
                for url in urls:
                    if any(host in url for host in ['mediafire', 'mega', 'drive.google', 'dropbox', 'zippyshare']):
                        download_links.append(url)
        
        # Remove duplicates and filter
        download_links = list(set(download_links))
        download_links = self.filter_download_links(download_links)
        
        return download_links
    
    def scrape_all_categories(self, max_pages_per_category: int = 5) -> List[Dict[str, Any]]:
        """Scrape all categories"""
        all_items = []
        
        for category in self.categories:
            self.logger.info(f"Starting scrape of category: {category}")
            
            try:
                items = self.scrape_category(category, max_pages_per_category)
                all_items.extend(items)
                
                self.logger.info(f"Completed category {category}: {len(items)} items")
                
            except Exception as e:
                self.logger.error(f"Failed to scrape category {category}: {e}")
            
            # Delay between categories
            time.sleep(5)
        
        self.logger.info(f"Total items scraped from FileCR: {len(all_items)}")
        return all_items