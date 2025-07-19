import mysql.connector
import pymysql
import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from config import DATABASE_CONFIG
import json
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.config = DATABASE_CONFIG
        self.connection = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(**self.config)
            self.logger.info("Database connection established")
            return True
        except mysql.connector.Error as e:
            self.logger.error(f"Database connection failed: {e}")
            try:
                # Fallback to pymysql
                self.connection = pymysql.connect(**self.config)
                self.logger.info("Database connection established with pymysql")
                return True
            except Exception as e2:
                self.logger.error(f"Fallback connection failed: {e2}")
                return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.logger.info("Database connection closed")
    
    def create_tables(self):
        """Create necessary tables for the bot"""
        tables = {
            'software_items': '''
                CREATE TABLE IF NOT EXISTS software_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    url VARCHAR(1000) NOT NULL UNIQUE,
                    source_site VARCHAR(100) NOT NULL,
                    category VARCHAR(100),
                    version VARCHAR(100),
                    file_size VARCHAR(50),
                    description TEXT,
                    download_links JSON,
                    metadata JSON,
                    scraped_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    download_status ENUM('pending', 'downloading', 'completed', 'failed', 'skipped') DEFAULT 'pending',
                    file_path VARCHAR(1000),
                    cloud_links JSON,
                    is_active BOOLEAN DEFAULT TRUE,
                    INDEX idx_source_site (source_site),
                    INDEX idx_category (category),
                    INDEX idx_download_status (download_status),
                    INDEX idx_scraped_date (scraped_date)
                )
            ''',
            'download_history': '''
                CREATE TABLE IF NOT EXISTS download_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    software_id INT,
                    download_url VARCHAR(1000),
                    file_name VARCHAR(500),
                    file_size BIGINT,
                    download_start TIMESTAMP,
                    download_end TIMESTAMP,
                    status ENUM('started', 'completed', 'failed', 'cancelled') DEFAULT 'started',
                    error_message TEXT,
                    file_path VARCHAR(1000),
                    cloud_upload_status JSON,
                    FOREIGN KEY (software_id) REFERENCES software_items(id) ON DELETE CASCADE,
                    INDEX idx_status (status),
                    INDEX idx_download_start (download_start)
                )
            ''',
            'upload_history': '''
                CREATE TABLE IF NOT EXISTS upload_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    software_id INT,
                    download_id INT,
                    cloud_provider ENUM('mediafire', 'mega', 'gdrive') NOT NULL,
                    upload_url VARCHAR(1000),
                    upload_start TIMESTAMP,
                    upload_end TIMESTAMP,
                    status ENUM('started', 'completed', 'failed') DEFAULT 'started',
                    error_message TEXT,
                    file_id VARCHAR(500),
                    share_link VARCHAR(1000),
                    FOREIGN KEY (software_id) REFERENCES software_items(id) ON DELETE CASCADE,
                    FOREIGN KEY (download_id) REFERENCES download_history(id) ON DELETE CASCADE,
                    INDEX idx_cloud_provider (cloud_provider),
                    INDEX idx_status (status)
                )
            ''',
            'scraping_stats': '''
                CREATE TABLE IF NOT EXISTS scraping_stats (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    site_name VARCHAR(100) NOT NULL,
                    scrape_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    items_found INT DEFAULT 0,
                    items_new INT DEFAULT 0,
                    items_updated INT DEFAULT 0,
                    items_failed INT DEFAULT 0,
                    execution_time INT,
                    status ENUM('started', 'completed', 'failed') DEFAULT 'started',
                    error_message TEXT,
                    INDEX idx_site_name (site_name),
                    INDEX idx_scrape_date (scrape_date)
                )
            ''',
            'bot_settings': '''
                CREATE TABLE IF NOT EXISTS bot_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_key VARCHAR(100) NOT NULL UNIQUE,
                    setting_value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            '''
        }
        
        try:
            cursor = self.connection.cursor()
            for table_name, create_sql in tables.items():
                cursor.execute(create_sql)
                self.logger.info(f"Table {table_name} created/verified")
            
            self.connection.commit()
            cursor.close()
            
            # Insert default settings
            self._insert_default_settings()
            
        except Exception as e:
            self.logger.error(f"Error creating tables: {e}")
            raise
    
    def _insert_default_settings(self):
        """Insert default bot settings"""
        default_settings = [
            ('last_full_scrape', None, 'Timestamp of last full scrape'),
            ('auto_download_enabled', 'true', 'Enable automatic downloads'),
            ('max_concurrent_downloads', '3', 'Maximum concurrent downloads'),
            ('auto_upload_enabled', 'true', 'Enable automatic uploads'),
            ('preferred_cloud_providers', '["mediafire", "mega", "gdrive"]', 'Preferred cloud storage providers'),
            ('min_file_size', '1024', 'Minimum file size to download (bytes)'),
            ('max_file_size', '5368709120', 'Maximum file size to download (bytes)'),
            ('excluded_extensions', '[]', 'File extensions to exclude'),
            ('notification_enabled', 'true', 'Enable notifications')
        ]
        
        try:
            cursor = self.connection.cursor()
            for key, value, description in default_settings:
                cursor.execute('''
                    INSERT IGNORE INTO bot_settings (setting_key, setting_value, description)
                    VALUES (%s, %s, %s)
                ''', (key, value, description))
            
            self.connection.commit()
            cursor.close()
            self.logger.info("Default settings inserted")
            
        except Exception as e:
            self.logger.error(f"Error inserting default settings: {e}")
    
    def insert_software_item(self, item_data: Dict[str, Any]) -> int:
        """Insert new software item"""
        try:
            cursor = self.connection.cursor()
            
            # Convert lists/dicts to JSON strings
            download_links = json.dumps(item_data.get('download_links', []))
            metadata = json.dumps(item_data.get('metadata', {}))
            
            sql = '''
                INSERT INTO software_items 
                (title, url, source_site, category, version, file_size, description, 
                 download_links, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    category = VALUES(category),
                    version = VALUES(version),
                    file_size = VALUES(file_size),
                    description = VALUES(description),
                    download_links = VALUES(download_links),
                    metadata = VALUES(metadata),
                    last_updated = CURRENT_TIMESTAMP
            '''
            
            cursor.execute(sql, (
                item_data['title'],
                item_data['url'],
                item_data['source_site'],
                item_data.get('category'),
                item_data.get('version'),
                item_data.get('file_size'),
                item_data.get('description'),
                download_links,
                metadata
            ))
            
            self.connection.commit()
            item_id = cursor.lastrowid or self.get_software_id_by_url(item_data['url'])
            cursor.close()
            
            return item_id
            
        except Exception as e:
            self.logger.error(f"Error inserting software item: {e}")
            raise
    
    def get_software_id_by_url(self, url: str) -> Optional[int]:
        """Get software ID by URL"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT id FROM software_items WHERE url = %s", (url,))
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else None
        except Exception as e:
            self.logger.error(f"Error getting software ID: {e}")
            return None
    
    def update_download_status(self, software_id: int, status: str, file_path: str = None):
        """Update download status"""
        try:
            cursor = self.connection.cursor()
            if file_path:
                cursor.execute('''
                    UPDATE software_items 
                    SET download_status = %s, file_path = %s 
                    WHERE id = %s
                ''', (status, file_path, software_id))
            else:
                cursor.execute('''
                    UPDATE software_items 
                    SET download_status = %s 
                    WHERE id = %s
                ''', (status, software_id))
            
            self.connection.commit()
            cursor.close()
            
        except Exception as e:
            self.logger.error(f"Error updating download status: {e}")
    
    def update_cloud_links(self, software_id: int, cloud_links: Dict[str, str]):
        """Update cloud storage links"""
        try:
            cursor = self.connection.cursor()
            cloud_links_json = json.dumps(cloud_links)
            cursor.execute('''
                UPDATE software_items 
                SET cloud_links = %s 
                WHERE id = %s
            ''', (cloud_links_json, software_id))
            
            self.connection.commit()
            cursor.close()
            
        except Exception as e:
            self.logger.error(f"Error updating cloud links: {e}")
    
    def get_pending_downloads(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending downloads"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute('''
                SELECT * FROM software_items 
                WHERE download_status = 'pending' AND is_active = TRUE
                ORDER BY scraped_date ASC
                LIMIT %s
            ''', (limit,))
            
            results = cursor.fetchall()
            cursor.close()
            
            # Parse JSON fields
            for result in results:
                if result['download_links']:
                    result['download_links'] = json.loads(result['download_links'])
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                if result['cloud_links']:
                    result['cloud_links'] = json.loads(result['cloud_links'])
                    
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting pending downloads: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            stats = {}
            
            # Total items
            cursor.execute("SELECT COUNT(*) as total FROM software_items WHERE is_active = TRUE")
            stats['total_items'] = cursor.fetchone()['total']
            
            # Items by status
            cursor.execute('''
                SELECT download_status, COUNT(*) as count 
                FROM software_items 
                WHERE is_active = TRUE 
                GROUP BY download_status
            ''')
            stats['by_status'] = {row['download_status']: row['count'] for row in cursor.fetchall()}
            
            # Items by source
            cursor.execute('''
                SELECT source_site, COUNT(*) as count 
                FROM software_items 
                WHERE is_active = TRUE 
                GROUP BY source_site
            ''')
            stats['by_source'] = {row['source_site']: row['count'] for row in cursor.fetchall()}
            
            # Recent scraping stats
            cursor.execute('''
                SELECT site_name, scrape_date, items_found, items_new 
                FROM scraping_stats 
                WHERE status = 'completed'
                ORDER BY scrape_date DESC 
                LIMIT 10
            ''')
            stats['recent_scrapes'] = cursor.fetchall()
            
            cursor.close()
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}
    
    def export_to_csv(self, filename: str, table_name: str = 'software_items'):
        """Export data to CSV"""
        try:
            query = f"SELECT * FROM {table_name} WHERE is_active = TRUE"
            df = pd.read_sql(query, self.connection)
            df.to_csv(filename, index=False)
            self.logger.info(f"Data exported to {filename}")
            
        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old inactive data"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                DELETE FROM software_items 
                WHERE is_active = FALSE 
                AND last_updated < DATE_SUB(NOW(), INTERVAL %s DAY)
            ''', (days,))
            
            deleted_count = cursor.rowcount
            self.connection.commit()
            cursor.close()
            
            self.logger.info(f"Cleaned up {deleted_count} old records")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up data: {e}")
            return 0

# Initialize database manager
db_manager = DatabaseManager()