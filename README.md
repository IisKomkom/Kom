# Freeware Bot - Automated Scraper and Downloader

A comprehensive bot that automatically scrapes, downloads, and uploads free software from multiple trusted sources including FileCR, Nasbandia, Downloadly, AppTorent.ru and other freeware sites.

## Features

### 🔍 Multi-Site Scraping
- **FileCR**: Windows, macOS, Android software and games
- **Nasbandia**: Software, games, and mobile applications
- **Downloadly**: Persian software repository
- **AppTorent.ru**: Russian freeware collection
- **Additional Sites**: Softpedia, MajorGeeks, TechSpot, Ninite, PortableApps, FossHub, SourceForge

### 📥 Intelligent Download Management
- Automatic detection of direct download links
- Support for multiple hosting services (MediaFire, MEGA, Google Drive, Dropbox, ZippyShare)
- Concurrent downloads with progress tracking
- File verification and validation
- Resume incomplete downloads
- Size and extension filtering

### ☁️ Cloud Storage Integration
- **MediaFire**: Upload and share links generation
- **MEGA**: Secure cloud storage with encryption
- **Google Drive**: Enterprise-grade storage with API integration
- **Rclone Integration**: Universal cloud storage support

### 🗄️ Database Management
- MySQL/MariaDB support with comprehensive schema
- Automatic data deduplication
- Download and upload history tracking
- Statistics and analytics
- CSV export functionality
- Data cleanup and maintenance

### 🌐 HTML Report Generation
- Beautiful responsive web interface
- Search and filter functionality
- Category-based organization
- Bootstrap 5 with modern design
- Mobile-friendly interface

### ⏰ Automated Scheduling
- Weekly/daily/hourly scraping schedules
- Automatic batch downloads and uploads
- Maintenance tasks automation
- Configurable timing and intervals

## Installation

### Prerequisites
- Python 3.8+
- MySQL/MariaDB database
- Google Chrome browser (for Selenium)
- rclone (for cloud storage)

### Quick Setup

1. **Clone the repository:**
```bash
git clone https://github.com/your-username/freeware-bot.git
cd freeware-bot
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Install system dependencies:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install mysql-server rclone google-chrome-stable

# CentOS/RHEL
sudo yum install mysql-server rclone google-chrome-stable

# macOS
brew install mysql rclone
brew install --cask google-chrome
```

4. **Setup database:**
```bash
mysql -u root -p
CREATE DATABASE freeware_bot;
CREATE USER 'freeware_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON freeware_bot.* TO 'freeware_user'@'localhost';
FLUSH PRIVILEGES;
```

5. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

6. **Initialize the bot:**
```bash
python main_bot.py --mode scrape
```

## Configuration

### Environment Variables (.env)

```bash
# Database Configuration
DB_HOST=localhost
DB_USER=freeware_user
DB_PASSWORD=your_password
DB_NAME=freeware_bot
DB_PORT=3306

# MediaFire Configuration
MEDIAFIRE_EMAIL=your_email@example.com
MEDIAFIRE_PASSWORD=your_password
MEDIAFIRE_API_KEY=your_api_key

# MEGA Configuration
MEGA_EMAIL=your_email@example.com
MEGA_PASSWORD=your_password

# Google Drive Configuration
GDRIVE_SERVICE_ACCOUNT=path/to/service-account.json
GDRIVE_FOLDER_ID=your_folder_id

# Rclone Configuration
RCLONE_CONFIG=~/.config/rclone/rclone.conf
```

### Advanced Configuration (config.py)

```python
# Scraping Configuration
SCRAPING_CONFIG = {
    'delay_between_requests': 2,  # Seconds
    'max_retries': 3,
    'timeout': 30,
    'concurrent_downloads': 3
}

# Download Configuration
DOWNLOAD_CONFIG = {
    'max_file_size': 5 * 1024 * 1024 * 1024,  # 5GB
    'allowed_extensions': ['.exe', '.msi', '.dmg', '.app', '.apk', '.zip', '.rar'],
    'download_folder': './downloads/'
}

# Schedule Configuration
SCHEDULE_CONFIG = {
    'update_frequency': 'weekly',  # weekly, daily, hourly
    'update_day': 'monday',
    'update_time': '02:00'
}
```

## Usage

### Command Line Interface

```bash
# Run as daemon (continuous operation)
python main_bot.py --mode daemon

# One-time scraping
python main_bot.py --mode scrape

# Download pending files
python main_bot.py --mode download --max-items 20

# Upload downloaded files
python main_bot.py --mode upload --max-items 10

# Check status
python main_bot.py --mode status
```

### Python API

```python
from main_bot import FreewareBot

# Initialize bot
bot = FreewareBot()

# Initialize database
bot.initialize_database()

# Run full scrape
results = bot.run_full_scrape()
print(f"Scraped {results['total_items']} items")

# Download batch
download_results = bot.run_download_batch(max_downloads=10)
print(f"Downloaded {download_results['downloaded']} files")

# Upload batch
upload_results = bot.run_upload_batch(max_uploads=5)
print(f"Uploaded {upload_results['uploaded']} files")

# Generate HTML report
bot.generate_html_report()
```

## Architecture

### Core Components

```
freeware-bot/
├── main_bot.py              # Main bot orchestrator
├── config.py                # Configuration management
├── database.py              # Database operations
├── downloader.py            # File download manager
├── cloud_uploader.py        # Cloud storage integration
├── html_generator.py        # HTML report generation
├── scrapers/
│   ├── base_scraper.py      # Base scraper class
│   ├── filecr_scraper.py    # FileCR specific scraper
│   ├── nasbandia_scraper.py # Nasbandia scraper
│   └── ...                  # Other site scrapers
├── templates/               # HTML templates
├── html_output/             # Generated HTML files
├── downloads/               # Downloaded files
└── logs/                    # Log files
```

### Database Schema

#### software_items
- `id`: Primary key
- `title`: Software title
- `url`: Original source URL
- `source_site`: Source website
- `category`: Software category
- `version`: Version number
- `file_size`: File size
- `description`: Description text
- `download_links`: JSON array of download URLs
- `metadata`: JSON object with additional info
- `download_status`: pending/downloading/completed/failed
- `file_path`: Local file path
- `cloud_links`: JSON object with cloud storage links

#### download_history
- Download tracking and statistics

#### upload_history
- Upload tracking for each cloud provider

#### scraping_stats
- Scraping performance metrics

## Cloud Storage Setup

### MediaFire
1. Create MediaFire account
2. Get API key from developer portal
3. Configure credentials in .env

### MEGA
1. Create MEGA account
2. Install MEGA SDK (optional)
3. Configure credentials in .env

### Google Drive
1. Create Google Cloud Project
2. Enable Drive API
3. Create service account
4. Download service account JSON
5. Share target folder with service account email

### Rclone Setup
```bash
# Configure rclone interactively
rclone config

# Test configuration
rclone ls mediafire:
rclone ls mega:
rclone ls gdrive:
```

## HTML Report Features

### Generated Pages
- **index.html**: Homepage with statistics and latest software
- **software_list.html**: Complete software listing with search/sort
- **category_*.html**: Category-specific pages
- **style.css**: Custom styling

### Features
- Responsive Bootstrap 5 design
- Real-time search functionality
- Sort by name, category, date
- Download buttons for each software
- Statistics dashboard
- Mobile-friendly interface

## Monitoring and Maintenance

### Logging
- Comprehensive logging to files and console
- Rotating log files with size limits
- Different log levels (DEBUG, INFO, WARNING, ERROR)

### Statistics
```bash
# View current statistics
python main_bot.py --mode status

# Database statistics
python -c "from database import db_manager; print(db_manager.get_stats())"

# Download statistics
python -c "from downloader import downloader; print(downloader.get_download_stats())"
```

### Maintenance Tasks
- Automatic cleanup of old data
- Failed download cleanup
- Database optimization
- Log rotation
- CSV data export

## Troubleshooting

### Common Issues

1. **Database Connection Error**
```bash
# Check MySQL service
sudo systemctl status mysql
sudo systemctl start mysql

# Test connection
mysql -u freeware_user -p freeware_bot
```

2. **Chrome/Selenium Issues**
```bash
# Update Chrome
sudo apt-get update && sudo apt-get upgrade google-chrome-stable

# Check ChromeDriver
python -c "from selenium import webdriver; driver = webdriver.Chrome(); driver.quit()"
```

3. **rclone Configuration**
```bash
# Test rclone remotes
rclone config show
rclone test mediafire:
rclone test mega:
rclone test gdrive:
```

4. **Permission Issues**
```bash
# Fix download folder permissions
chmod -R 755 downloads/
chown -R $USER:$USER downloads/
```

### Performance Optimization

1. **Database Optimization**
```sql
-- Add indexes for better performance
CREATE INDEX idx_title ON software_items(title);
CREATE INDEX idx_scraped_date ON software_items(scraped_date);
CREATE INDEX idx_download_status ON software_items(download_status);
```

2. **Download Optimization**
```python
# Increase concurrent downloads (config.py)
DOWNLOAD_CONFIG = {
    'concurrent_downloads': 5  # Increase from 3
}
```

3. **Scraping Optimization**
```python
# Reduce delay for faster scraping
SCRAPING_CONFIG = {
    'delay_between_requests': 1  # Reduce from 2
}
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/new-scraper`)
3. Add new scraper in `scrapers/` directory
4. Follow existing scraper pattern
5. Add tests
6. Submit pull request

### Adding New Scrapers

```python
# Example: new_site_scraper.py
from scrapers.base_scraper import BaseScraper

class NewSiteScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            site_name='newsite',
            base_url='https://newsite.com',
            selectors={
                'title': 'h1.title',
                'download_link': 'a.download',
                # ... other selectors
            }
        )
    
    def scrape_all_categories(self):
        # Implement site-specific scraping logic
        pass
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This bot is for educational and personal use only. Users are responsible for:
- Respecting website terms of service
- Following copyright laws
- Using appropriate rate limiting
- Not overloading target servers

## Support

- 📧 Email: support@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/your-username/freeware-bot/issues)
- 📖 Documentation: [Wiki](https://github.com/your-username/freeware-bot/wiki)
- 💬 Discord: [Community Server](https://discord.gg/your-server)

## Roadmap

- [ ] Add support for more freeware sites
- [ ] Implement torrent download support
- [ ] Add web interface for configuration
- [ ] Docker containerization
- [ ] Kubernetes deployment support
- [ ] API endpoints for external integration
- [ ] Machine learning for better categorization
- [ ] Virus scanning integration
- [ ] Download mirror validation
- [ ] Advanced filtering and tagging system