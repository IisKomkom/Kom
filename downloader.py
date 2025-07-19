import os
import requests
import time
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from tqdm import tqdm
import shutil
from pathlib import Path
import re
from config import DOWNLOAD_CONFIG, SCRAPING_CONFIG
import mimetypes

class FileDownloader:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update(SCRAPING_CONFIG['headers'])
        self.download_folder = Path(DOWNLOAD_CONFIG['download_folder'])
        self.download_folder.mkdir(exist_ok=True)
        
        # Threading lock for progress tracking
        self.progress_lock = threading.Lock()
        self.active_downloads = {}
        
    def download_file(self, url: str, filename: str = None, subfolder: str = None) -> Optional[Dict[str, Any]]:
        """Download a single file"""
        try:
            # Resolve final URL if redirected
            final_url = self.resolve_final_url(url)
            if not final_url:
                self.logger.error(f"Could not resolve URL: {url}")
                return None
            
            # Generate filename if not provided
            if not filename:
                filename = self.generate_filename(final_url)
            
            # Create download path
            download_path = self.download_folder
            if subfolder:
                download_path = download_path / subfolder
                download_path.mkdir(parents=True, exist_ok=True)
            
            file_path = download_path / filename
            
            # Check if file already exists
            if file_path.exists():
                self.logger.info(f"File already exists: {file_path}")
                return {
                    'success': True,
                    'file_path': str(file_path),
                    'file_size': file_path.stat().st_size,
                    'url': url,
                    'filename': filename,
                    'status': 'already_exists'
                }
            
            # Get file info
            file_info = self.get_file_info(final_url)
            if not file_info:
                self.logger.error(f"Could not get file info for: {final_url}")
                return None
            
            # Check file size limits
            if not self.check_file_size_limits(file_info.get('size', 0)):
                self.logger.warning(f"File size exceeds limits: {final_url}")
                return None
            
            # Check file extension
            if not self.check_file_extension(filename):
                self.logger.warning(f"File extension not allowed: {filename}")
                return None
            
            # Download the file
            download_result = self.download_with_progress(final_url, file_path, file_info)
            
            if download_result['success']:
                # Verify download
                if self.verify_download(file_path, file_info):
                    self.logger.info(f"Successfully downloaded: {filename}")
                    return {
                        'success': True,
                        'file_path': str(file_path),
                        'file_size': file_path.stat().st_size,
                        'url': url,
                        'filename': filename,
                        'status': 'downloaded',
                        'download_time': download_result.get('download_time'),
                        'average_speed': download_result.get('average_speed')
                    }
                else:
                    self.logger.error(f"Download verification failed: {filename}")
                    if file_path.exists():
                        file_path.unlink()
                    return None
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error downloading {url}: {e}")
            return None
    
    def resolve_final_url(self, url: str, max_redirects: int = 10) -> Optional[str]:
        """Resolve final URL following redirects"""
        try:
            response = self.session.head(url, allow_redirects=True, timeout=30)
            
            # Handle specific hosting sites
            if 'mediafire.com' in response.url:
                return self.resolve_mediafire_url(response.url)
            elif 'mega.nz' in response.url:
                return self.resolve_mega_url(response.url)
            elif 'drive.google.com' in response.url:
                return self.resolve_gdrive_url(response.url)
            elif 'dropbox.com' in response.url:
                return self.resolve_dropbox_url(response.url)
            elif 'zippyshare.com' in response.url:
                return self.resolve_zippyshare_url(response.url)
            
            return response.url
            
        except Exception as e:
            self.logger.error(f"Error resolving URL {url}: {e}")
            return None
    
    def resolve_mediafire_url(self, url: str) -> Optional[str]:
        """Resolve MediaFire download URL"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Look for direct download link
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # MediaFire download button
            download_link = soup.find('a', {'class': 'input'})
            if download_link and download_link.get('href'):
                return download_link['href']
                
            # Alternative selectors
            selectors = [
                'a[href*="download"]',
                '.download_link a',
                '#downloadButton'
            ]
            
            for selector in selectors:
                element = soup.select_one(selector)
                if element and element.get('href'):
                    return element['href']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error resolving MediaFire URL: {e}")
            return None
    
    def resolve_mega_url(self, url: str) -> Optional[str]:
        """Resolve MEGA download URL"""
        # MEGA requires special handling, return original URL for now
        return url
    
    def resolve_gdrive_url(self, url: str) -> Optional[str]:
        """Resolve Google Drive download URL"""
        try:
            # Extract file ID from URL
            file_id_match = re.search(r'/file/d/([a-zA-Z0-9-_]+)', url)
            if file_id_match:
                file_id = file_id_match.group(1)
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            
            return url
            
        except Exception as e:
            self.logger.error(f"Error resolving Google Drive URL: {e}")
            return None
    
    def resolve_dropbox_url(self, url: str) -> Optional[str]:
        """Resolve Dropbox download URL"""
        try:
            # Change dl=0 to dl=1 for direct download
            if 'dl=0' in url:
                return url.replace('dl=0', 'dl=1')
            elif '?dl=0' not in url and '&dl=1' not in url:
                separator = '&' if '?' in url else '?'
                return f"{url}{separator}dl=1"
            
            return url
            
        except Exception as e:
            self.logger.error(f"Error resolving Dropbox URL: {e}")
            return None
    
    def resolve_zippyshare_url(self, url: str) -> Optional[str]:
        """Resolve ZippyShare download URL"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for download button
            download_button = soup.find('a', {'id': 'dlbutton'})
            if download_button and download_button.get('href'):
                base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                return urljoin(base_url, download_button['href'])
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error resolving ZippyShare URL: {e}")
            return None
    
    def get_file_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get file information from URL"""
        try:
            response = self.session.head(url, timeout=30)
            
            file_info = {
                'url': url,
                'status_code': response.status_code,
                'headers': dict(response.headers)
            }
            
            # Get file size
            content_length = response.headers.get('content-length')
            if content_length:
                file_info['size'] = int(content_length)
            
            # Get content type
            content_type = response.headers.get('content-type')
            if content_type:
                file_info['content_type'] = content_type
            
            # Get filename from headers
            content_disposition = response.headers.get('content-disposition')
            if content_disposition:
                filename_match = re.search(r'filename[*]?=(?:["\']?)([^"\';]+)', content_disposition)
                if filename_match:
                    file_info['filename'] = filename_match.group(1)
            
            return file_info
            
        except Exception as e:
            self.logger.error(f"Error getting file info for {url}: {e}")
            return None
    
    def generate_filename(self, url: str) -> str:
        """Generate filename from URL"""
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename or filename == '/':
            # Generate filename from URL components
            filename = parsed_url.netloc.replace('.', '_')
            if parsed_url.query:
                filename += '_' + hashlib.md5(parsed_url.query.encode()).hexdigest()[:8]
            filename += '.bin'  # Default extension
        
        # Clean filename
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        # Ensure extension
        if '.' not in filename:
            filename += '.bin'
        
        return filename
    
    def check_file_size_limits(self, file_size: int) -> bool:
        """Check if file size is within limits"""
        max_size = DOWNLOAD_CONFIG['max_file_size']
        
        if file_size > max_size:
            self.logger.warning(f"File size {file_size} exceeds limit {max_size}")
            return False
        
        return True
    
    def check_file_extension(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        allowed_extensions = DOWNLOAD_CONFIG['allowed_extensions']
        
        if not allowed_extensions:  # If empty list, allow all
            return True
        
        file_extension = Path(filename).suffix.lower()
        return file_extension in allowed_extensions
    
    def download_with_progress(self, url: str, file_path: Path, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Download file with progress tracking"""
        try:
            start_time = time.time()
            
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = file_info.get('size', 0)
            chunk_size = DOWNLOAD_CONFIG['chunk_size']
            
            with open(file_path, 'wb') as f:
                if total_size > 0:
                    progress_bar = tqdm(
                        total=total_size,
                        unit='B',
                        unit_scale=True,
                        desc=file_path.name
                    )
                    
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress_bar.update(len(chunk))
                    
                    progress_bar.close()
                else:
                    # No content-length header
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
            
            download_time = time.time() - start_time
            file_size = file_path.stat().st_size
            average_speed = file_size / download_time if download_time > 0 else 0
            
            return {
                'success': True,
                'download_time': download_time,
                'average_speed': average_speed
            }
            
        except Exception as e:
            self.logger.error(f"Error downloading {url}: {e}")
            return {'success': False, 'error': str(e)}
    
    def verify_download(self, file_path: Path, file_info: Dict[str, Any]) -> bool:
        """Verify downloaded file"""
        try:
            if not file_path.exists():
                return False
            
            # Check file size if available
            expected_size = file_info.get('size')
            if expected_size:
                actual_size = file_path.stat().st_size
                if actual_size != expected_size:
                    self.logger.warning(f"File size mismatch: expected {expected_size}, got {actual_size}")
                    return False
            
            # Basic file validation
            if file_path.stat().st_size == 0:
                self.logger.error(f"Downloaded file is empty: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying download: {e}")
            return False
    
    def download_multiple(self, download_items: List[Dict[str, Any]], max_workers: int = None) -> List[Dict[str, Any]]:
        """Download multiple files concurrently"""
        if not max_workers:
            max_workers = DOWNLOAD_CONFIG['concurrent_downloads']
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_item = {}
            for item in download_items:
                if 'download_links' in item and item['download_links']:
                    # Download first available link
                    url = item['download_links'][0]
                    subfolder = item.get('source_site', 'unknown')
                    filename = self.sanitize_filename(item.get('title', ''))
                    
                    future = executor.submit(self.download_file, url, filename, subfolder)
                    future_to_item[future] = item
            
            # Collect results
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    if result:
                        result['item_data'] = item
                        results.append(result)
                    else:
                        self.logger.error(f"Failed to download: {item.get('title', 'Unknown')}")
                        
                except Exception as e:
                    self.logger.error(f"Download task failed for {item.get('title', 'Unknown')}: {e}")
        
        return results
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem"""
        # Remove/replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        
        # Ensure it's not empty
        if not filename.strip():
            filename = 'download'
        
        return filename.strip()
    
    def get_download_stats(self) -> Dict[str, Any]:
        """Get download statistics"""
        stats = {
            'total_files': 0,
            'total_size': 0,
            'successful_downloads': 0,
            'failed_downloads': 0
        }
        
        if self.download_folder.exists():
            for file_path in self.download_folder.rglob('*'):
                if file_path.is_file():
                    stats['total_files'] += 1
                    stats['total_size'] += file_path.stat().st_size
        
        return stats
    
    def cleanup_failed_downloads(self):
        """Clean up incomplete or corrupted downloads"""
        cleaned_count = 0
        
        if self.download_folder.exists():
            for file_path in self.download_folder.rglob('*'):
                if file_path.is_file():
                    # Check if file is empty or very small
                    if file_path.stat().st_size < 1024:  # Less than 1KB
                        try:
                            file_path.unlink()
                            cleaned_count += 1
                            self.logger.info(f"Removed incomplete download: {file_path}")
                        except Exception as e:
                            self.logger.error(f"Failed to remove file {file_path}: {e}")
        
        return cleaned_count

# Initialize downloader
downloader = FileDownloader()