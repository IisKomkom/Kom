#!/usr/bin/env python3
"""
Freeware Bot - Automated scraper and downloader for freeware sites
Scrapes data from FileCR, Nasbandia, Downloadly, AppTorent and other freeware sites
Downloads files and uploads to MediaFire, MEGA, and Google Drive
"""

import logging
import schedule
import time
import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any
import signal
import threading
import json

# Import all modules
from config import SCHEDULE_CONFIG, LOGGING_CONFIG
from database import db_manager
from downloader import downloader
from cloud_uploader import cloud_uploader
from scrapers.filecr_scraper import FilecrScraper
from html_generator import HTMLGenerator

# Setup logging
def setup_logging():
    """Setup comprehensive logging"""
    logging.basicConfig(
        level=getattr(logging, LOGGING_CONFIG['level']),
        format=LOGGING_CONFIG['format'],
        handlers=[
            logging.FileHandler(LOGGING_CONFIG['file']),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Setup rotating log file
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        LOGGING_CONFIG['file'],
        maxBytes=LOGGING_CONFIG['max_size'],
        backupCount=LOGGING_CONFIG['backup_count']
    )
    file_handler.setFormatter(logging.Formatter(LOGGING_CONFIG['format']))
    
    logger = logging.getLogger()
    logger.handlers = [file_handler, logging.StreamHandler(sys.stdout)]
    
    return logger

class FreewareBot:
    def __init__(self):
        self.logger = setup_logging()
        self.running = False
        self.scrapers = {}
        self.setup_scrapers()
        self.setup_signal_handlers()
        
        # Statistics
        self.stats = {
            'total_scraped': 0,
            'total_downloaded': 0,
            'total_uploaded': 0,
            'errors': 0,
            'start_time': None
        }
        
    def setup_scrapers(self):
        """Initialize all scrapers"""
        self.scrapers = {
            'filecr': FilecrScraper(),
            # Add other scrapers here as they are implemented
        }
        self.logger.info(f"Initialized {len(self.scrapers)} scrapers")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
    
    def initialize_database(self):
        """Initialize database connection and tables"""
        try:
            if db_manager.connect():
                db_manager.create_tables()
                self.logger.info("Database initialized successfully")
                return True
            else:
                self.logger.error("Failed to connect to database")
                return False
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            return False
    
    def run_full_scrape(self) -> Dict[str, Any]:
        """Run full scrape of all sites"""
        self.logger.info("Starting full scrape of all sites")
        start_time = datetime.now()
        
        results = {
            'start_time': start_time,
            'scrapers': {},
            'total_items': 0,
            'new_items': 0,
            'errors': 0
        }
        
        for site_name, scraper in self.scrapers.items():
            self.logger.info(f"Starting scrape of {site_name}")
            scraper_start = datetime.now()
            
            try:
                # Record scraping start in database
                scrape_stat_id = self._record_scrape_start(site_name)
                
                # Perform scraping
                if hasattr(scraper, 'scrape_all_categories'):
                    items = scraper.scrape_all_categories()
                else:
                    items = []
                
                # Process scraped items
                new_items = 0
                for item in items:
                    try:
                        item_id = db_manager.insert_software_item(item)
                        if item_id:
                            new_items += 1
                    except Exception as e:
                        self.logger.error(f"Failed to save item {item.get('title', 'Unknown')}: {e}")
                        results['errors'] += 1
                
                scraper_time = (datetime.now() - scraper_start).total_seconds()
                
                # Update scraping stats
                self._record_scrape_end(scrape_stat_id, len(items), new_items, 0, scraper_time)
                
                results['scrapers'][site_name] = {
                    'items_found': len(items),
                    'new_items': new_items,
                    'time_taken': scraper_time,
                    'status': 'completed'
                }
                
                results['total_items'] += len(items)
                results['new_items'] += new_items
                
                self.logger.info(f"Completed {site_name}: {len(items)} items, {new_items} new")
                
            except Exception as e:
                self.logger.error(f"Scraping failed for {site_name}: {e}")
                results['scrapers'][site_name] = {
                    'status': 'failed',
                    'error': str(e)
                }
                results['errors'] += 1
                
                # Record failure
                if 'scrape_stat_id' in locals():
                    self._record_scrape_end(scrape_stat_id, 0, 0, 1, 0, str(e))
            
            finally:
                # Clean up scraper resources
                if hasattr(scraper, 'close'):
                    scraper.close()
        
        results['end_time'] = datetime.now()
        results['total_time'] = (results['end_time'] - start_time).total_seconds()
        
        self.stats['total_scraped'] += results['total_items']
        
        self.logger.info(f"Full scrape completed: {results['total_items']} items, {results['new_items']} new")
        return results
    
    def run_download_batch(self, max_downloads: int = 10) -> Dict[str, Any]:
        """Download a batch of pending files"""
        self.logger.info(f"Starting download batch (max {max_downloads})")
        
        # Get pending downloads
        pending_items = db_manager.get_pending_downloads(max_downloads)
        
        if not pending_items:
            self.logger.info("No pending downloads found")
            return {'downloaded': 0, 'failed': 0, 'items': []}
        
        results = {
            'downloaded': 0,
            'failed': 0,
            'items': []
        }
        
        for item in pending_items:
            try:
                # Update status to downloading
                db_manager.update_download_status(item['id'], 'downloading')
                
                # Download file
                download_result = downloader.download_file(
                    url=item['download_links'][0] if item['download_links'] else None,
                    filename=downloader.sanitize_filename(item['title']),
                    subfolder=item['source_site']
                )
                
                if download_result and download_result['success']:
                    # Update database with successful download
                    db_manager.update_download_status(
                        item['id'], 
                        'completed', 
                        download_result['file_path']
                    )
                    
                    results['downloaded'] += 1
                    self.stats['total_downloaded'] += 1
                    
                    # Queue for upload
                    if download_result['file_path']:
                        self._queue_for_upload(item['id'], download_result['file_path'])
                    
                    self.logger.info(f"Successfully downloaded: {item['title']}")
                    
                else:
                    # Update database with failed download
                    db_manager.update_download_status(item['id'], 'failed')
                    results['failed'] += 1
                    self.logger.error(f"Failed to download: {item['title']}")
                
                results['items'].append({
                    'title': item['title'],
                    'status': 'success' if download_result and download_result['success'] else 'failed',
                    'result': download_result
                })
                
            except Exception as e:
                self.logger.error(f"Error downloading {item['title']}: {e}")
                db_manager.update_download_status(item['id'], 'failed')
                results['failed'] += 1
                self.stats['errors'] += 1
        
        self.logger.info(f"Download batch completed: {results['downloaded']} downloaded, {results['failed']} failed")
        return results
    
    def run_upload_batch(self, max_uploads: int = 5) -> Dict[str, Any]:
        """Upload a batch of downloaded files"""
        self.logger.info(f"Starting upload batch (max {max_uploads})")
        
        # Get completed downloads that haven't been uploaded
        completed_items = db_manager.get_pending_downloads(max_uploads)  # You'll need to modify this method
        completed_items = [item for item in completed_items if item['download_status'] == 'completed' and item['file_path']]
        
        if not completed_items:
            self.logger.info("No files ready for upload")
            return {'uploaded': 0, 'failed': 0, 'items': []}
        
        results = {
            'uploaded': 0,
            'failed': 0,
            'items': []
        }
        
        cloud_providers = ['mediafire', 'mega', 'gdrive']
        
        for item in completed_items[:max_uploads]:
            try:
                cloud_links = {}
                upload_success = False
                
                for provider in cloud_providers:
                    try:
                        upload_result = cloud_uploader.upload_file(
                            item['file_path'],
                            provider,
                            f"freeware_bot/{item['source_site']}/{item['title']}"
                        )
                        
                        if upload_result['success']:
                            cloud_links[provider] = upload_result.get('share_link', '')
                            upload_success = True
                            self.logger.info(f"Uploaded {item['title']} to {provider}")
                        else:
                            self.logger.error(f"Failed to upload {item['title']} to {provider}: {upload_result.get('error', 'Unknown error')}")
                            
                    except Exception as e:
                        self.logger.error(f"Upload error for {provider}: {e}")
                
                # Update database with cloud links
                if cloud_links:
                    db_manager.update_cloud_links(item['id'], cloud_links)
                    results['uploaded'] += 1
                    self.stats['total_uploaded'] += 1
                else:
                    results['failed'] += 1
                
                results['items'].append({
                    'title': item['title'],
                    'cloud_links': cloud_links,
                    'status': 'success' if upload_success else 'failed'
                })
                
            except Exception as e:
                self.logger.error(f"Error uploading {item['title']}: {e}")
                results['failed'] += 1
                self.stats['errors'] += 1
        
        self.logger.info(f"Upload batch completed: {results['uploaded']} uploaded, {results['failed']} failed")
        return results
    
    def generate_html_report(self):
        """Generate HTML report of all software"""
        try:
            self.logger.info("Generating HTML report")
            
            html_generator = HTMLGenerator()
            report_path = html_generator.generate_full_report()
            
            if report_path:
                self.logger.info(f"HTML report generated: {report_path}")
            else:
                self.logger.error("Failed to generate HTML report")
                
        except Exception as e:
            self.logger.error(f"Error generating HTML report: {e}")
    
    def run_maintenance(self):
        """Run maintenance tasks"""
        self.logger.info("Running maintenance tasks")
        
        try:
            # Clean up old data
            cleaned_count = db_manager.cleanup_old_data(30)
            self.logger.info(f"Cleaned up {cleaned_count} old records")
            
            # Clean up failed downloads
            failed_cleaned = downloader.cleanup_failed_downloads()
            self.logger.info(f"Cleaned up {failed_cleaned} failed downloads")
            
            # Export data to CSV
            csv_filename = f"freeware_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            db_manager.export_to_csv(csv_filename)
            self.logger.info(f"Data exported to {csv_filename}")
            
            # Generate HTML report
            self.generate_html_report()
            
        except Exception as e:
            self.logger.error(f"Maintenance error: {e}")
    
    def _record_scrape_start(self, site_name: str) -> int:
        """Record scraping start in database"""
        # This would need to be implemented in database.py
        pass
    
    def _record_scrape_end(self, scrape_id: int, items_found: int, items_new: int, items_failed: int, execution_time: float, error_message: str = None):
        """Record scraping end in database"""
        # This would need to be implemented in database.py
        pass
    
    def _queue_for_upload(self, software_id: int, file_path: str):
        """Queue file for upload"""
        # This could be implemented as a separate upload queue
        pass
    
    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report"""
        try:
            db_stats = db_manager.get_stats()
            download_stats = downloader.get_download_stats()
            upload_stats = cloud_uploader.get_upload_stats()
            
            uptime = None
            if self.stats['start_time']:
                uptime = (datetime.now() - self.stats['start_time']).total_seconds()
            
            return {
                'bot_stats': self.stats,
                'uptime_seconds': uptime,
                'database_stats': db_stats,
                'download_stats': download_stats,
                'upload_stats': upload_stats,
                'running': self.running
            }
            
        except Exception as e:
            self.logger.error(f"Error getting status report: {e}")
            return {'error': str(e)}
    
    def setup_schedule(self):
        """Setup scheduled tasks"""
        if SCHEDULE_CONFIG['update_frequency'] == 'weekly':
            schedule.every().week.at(SCHEDULE_CONFIG['update_time']).do(self.run_full_scrape)
        elif SCHEDULE_CONFIG['update_frequency'] == 'daily':
            schedule.every().day.at(SCHEDULE_CONFIG['update_time']).do(self.run_full_scrape)
        elif SCHEDULE_CONFIG['update_frequency'] == 'hourly':
            schedule.every().hour.do(self.run_full_scrape)
        
        # Download and upload batches every hour
        schedule.every().hour.do(self.run_download_batch)
        schedule.every(2).hours.do(self.run_upload_batch)
        
        # Maintenance tasks daily
        schedule.every().day.at("03:00").do(self.run_maintenance)
        
        self.logger.info("Scheduled tasks configured")
    
    def start(self):
        """Start the bot"""
        self.logger.info("Starting Freeware Bot")
        self.stats['start_time'] = datetime.now()
        self.running = True
        
        # Initialize database
        if not self.initialize_database():
            self.logger.error("Failed to initialize database, exiting")
            return False
        
        # Setup scheduled tasks
        self.setup_schedule()
        
        # Run initial tasks
        self.logger.info("Running initial scrape")
        self.run_full_scrape()
        
        # Start scheduler loop
        self.logger.info("Starting scheduler loop")
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(SCHEDULE_CONFIG['check_interval'])
                
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Scheduler error: {e}")
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """Stop the bot"""
        self.logger.info("Stopping Freeware Bot")
        self.running = False
        
        # Close database connection
        if db_manager.connection:
            db_manager.disconnect()
        
        # Close scrapers
        for scraper in self.scrapers.values():
            if hasattr(scraper, 'close'):
                scraper.close()
        
        self.logger.info("Bot stopped successfully")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Freeware Bot - Automated scraper and downloader')
    parser.add_argument('--mode', choices=['daemon', 'scrape', 'download', 'upload', 'status'], 
                       default='daemon', help='Operation mode')
    parser.add_argument('--max-items', type=int, default=10, 
                       help='Maximum items to process in batch modes')
    
    args = parser.parse_args()
    
    bot = FreewareBot()
    
    if args.mode == 'daemon':
        # Run as daemon with scheduled tasks
        bot.start()
        
    elif args.mode == 'scrape':
        # Run one-time scraping
        if not bot.initialize_database():
            sys.exit(1)
        result = bot.run_full_scrape()
        print(json.dumps(result, indent=2, default=str))
        
    elif args.mode == 'download':
        # Run one-time download batch
        if not bot.initialize_database():
            sys.exit(1)
        result = bot.run_download_batch(args.max_items)
        print(json.dumps(result, indent=2, default=str))
        
    elif args.mode == 'upload':
        # Run one-time upload batch
        if not bot.initialize_database():
            sys.exit(1)
        result = bot.run_upload_batch(args.max_items)
        print(json.dumps(result, indent=2, default=str))
        
    elif args.mode == 'status':
        # Show status report
        if not bot.initialize_database():
            sys.exit(1)
        status = bot.get_status_report()
        print(json.dumps(status, indent=2, default=str))

if __name__ == '__main__':
    main()