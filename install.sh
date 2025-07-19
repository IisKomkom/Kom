#!/bin/bash

# Freeware Bot - Automated Installer
# This script automatically sets up the Freeware Bot environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root"
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get >/dev/null 2>&1; then
            OS="ubuntu"
            PACKAGE_MANAGER="apt-get"
        elif command -v yum >/dev/null 2>&1; then
            OS="centos"
            PACKAGE_MANAGER="yum"
        elif command -v dnf >/dev/null 2>&1; then
            OS="fedora"
            PACKAGE_MANAGER="dnf"
        else
            log_error "Unsupported Linux distribution"
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PACKAGE_MANAGER="brew"
    else
        log_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    log_info "Detected OS: $OS"
}

# Check and install dependencies
install_system_dependencies() {
    log_info "Installing system dependencies..."
    
    case $OS in
        "ubuntu")
            sudo apt-get update
            sudo apt-get install -y \
                python3 \
                python3-pip \
                python3-venv \
                mysql-server \
                mysql-client \
                wget \
                curl \
                unzip \
                gnupg \
                software-properties-common
            
            # Install Google Chrome
            if ! command -v google-chrome >/dev/null 2>&1; then
                log_info "Installing Google Chrome..."
                wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
                echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
                sudo apt-get update
                sudo apt-get install -y google-chrome-stable
            fi
            
            # Install rclone
            if ! command -v rclone >/dev/null 2>&1; then
                log_info "Installing rclone..."
                curl https://rclone.org/install.sh | sudo bash
            fi
            ;;
            
        "centos")
            sudo yum update -y
            sudo yum install -y \
                python3 \
                python3-pip \
                mysql-server \
                mysql \
                wget \
                curl \
                unzip
            
            # Install Google Chrome
            if ! command -v google-chrome >/dev/null 2>&1; then
                log_info "Installing Google Chrome..."
                sudo yum install -y https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
            fi
            
            # Install rclone
            if ! command -v rclone >/dev/null 2>&1; then
                log_info "Installing rclone..."
                curl https://rclone.org/install.sh | sudo bash
            fi
            ;;
            
        "fedora")
            sudo dnf update -y
            sudo dnf install -y \
                python3 \
                python3-pip \
                mysql-server \
                mysql \
                wget \
                curl \
                unzip
            
            # Install Google Chrome
            if ! command -v google-chrome >/dev/null 2>&1; then
                log_info "Installing Google Chrome..."
                sudo dnf install -y https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
            fi
            
            # Install rclone
            if ! command -v rclone >/dev/null 2>&1; then
                log_info "Installing rclone..."
                curl https://rclone.org/install.sh | sudo bash
            fi
            ;;
            
        "macos")
            # Check if Homebrew is installed
            if ! command -v brew >/dev/null 2>&1; then
                log_info "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            
            # Install dependencies
            brew update
            brew install python3 mysql rclone wget curl
            
            # Install Google Chrome
            if ! command -v google-chrome >/dev/null 2>&1; then
                log_info "Installing Google Chrome..."
                brew install --cask google-chrome
            fi
            ;;
    esac
    
    log_success "System dependencies installed"
}

# Setup Python virtual environment
setup_python_env() {
    log_info "Setting up Python virtual environment..."
    
    # Create virtual environment
    python3 -m venv freeware_env
    
    # Activate virtual environment
    source freeware_env/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Python dependencies
    pip install -r requirements.txt
    
    log_success "Python environment setup complete"
}

# Setup MySQL database
setup_database() {
    log_info "Setting up MySQL database..."
    
    # Start MySQL service
    case $OS in
        "ubuntu"|"fedora")
            sudo systemctl start mysql
            sudo systemctl enable mysql
            ;;
        "centos")
            sudo systemctl start mysqld
            sudo systemctl enable mysqld
            ;;
        "macos")
            brew services start mysql
            ;;
    esac
    
    # Check if MySQL is running
    if ! mysqladmin ping >/dev/null 2>&1; then
        log_warning "MySQL is not running. Please start MySQL manually and run this script again."
        return 1
    fi
    
    # Prompt for MySQL root password
    echo -n "Enter MySQL root password (leave empty if no password): "
    read -s MYSQL_ROOT_PASSWORD
    echo
    
    # Create database and user
    DB_NAME="freeware_bot"
    DB_USER="freeware_user"
    DB_PASSWORD=$(openssl rand -base64 12)
    
    if [[ -z "$MYSQL_ROOT_PASSWORD" ]]; then
        mysql -u root << EOF
CREATE DATABASE IF NOT EXISTS $DB_NAME;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF
    else
        mysql -u root -p$MYSQL_ROOT_PASSWORD << EOF
CREATE DATABASE IF NOT EXISTS $DB_NAME;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF
    fi
    
    # Save database credentials
    echo "DB_PASSWORD=$DB_PASSWORD" >> .env.local
    
    log_success "Database setup complete"
    log_info "Database credentials saved to .env.local"
}

# Setup configuration
setup_config() {
    log_info "Setting up configuration..."
    
    # Copy example environment file
    if [[ ! -f .env ]]; then
        cp .env.example .env
        log_info "Created .env file from template"
    fi
    
    # Update database configuration if credentials were generated
    if [[ -f .env.local ]]; then
        source .env.local
        sed -i.bak "s/DB_PASSWORD=your_password/DB_PASSWORD=$DB_PASSWORD/" .env
        sed -i.bak "s/DB_USER=root/DB_USER=freeware_user/" .env
        sed -i.bak "s/DB_NAME=freeware_bot/DB_NAME=freeware_bot/" .env
        rm .env.bak
        rm .env.local
    fi
    
    log_success "Configuration setup complete"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p downloads
    mkdir -p logs
    mkdir -p templates
    mkdir -p html_output
    mkdir -p scrapers
    
    # Set permissions
    chmod 755 downloads logs templates html_output scrapers
    
    log_success "Directories created"
}

# Setup rclone configuration
setup_rclone() {
    log_info "Setting up rclone configuration..."
    
    if [[ ! -f ~/.config/rclone/rclone.conf ]]; then
        log_warning "rclone not configured. You can configure it later by running: rclone config"
        log_info "For automatic cloud uploads, configure at least one of: MediaFire, MEGA, Google Drive"
    else
        log_success "rclone already configured"
    fi
}

# Test installation
test_installation() {
    log_info "Testing installation..."
    
    # Activate virtual environment
    source freeware_env/bin/activate
    
    # Test Python imports
    python3 -c "import requests, beautifulsoup4, selenium, mysql.connector, schedule" 2>/dev/null
    if [[ $? -eq 0 ]]; then
        log_success "Python dependencies test passed"
    else
        log_error "Python dependencies test failed"
        return 1
    fi
    
    # Test database connection
    python3 -c "
from database import db_manager
if db_manager.connect():
    print('Database connection successful')
    db_manager.disconnect()
else:
    print('Database connection failed')
    exit(1)
" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        log_success "Database connection test passed"
    else
        log_error "Database connection test failed"
        return 1
    fi
    
    # Test Chrome/Selenium
    python3 -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
try:
    driver = webdriver.Chrome(options=options)
    driver.quit()
    print('Chrome/Selenium test passed')
except Exception as e:
    print(f'Chrome/Selenium test failed: {e}')
    exit(1)
" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        log_success "Chrome/Selenium test passed"
    else
        log_error "Chrome/Selenium test failed"
        return 1
    fi
    
    log_success "All tests passed!"
}

# Create systemd service (Linux only)
create_service() {
    if [[ "$OS" != "macos" ]]; then
        log_info "Creating systemd service..."
        
        CURRENT_DIR=$(pwd)
        USER_NAME=$(whoami)
        
        sudo tee /etc/systemd/system/freeware-bot.service > /dev/null << EOF
[Unit]
Description=Freeware Bot - Automated Scraper and Downloader
After=network.target mysql.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$CURRENT_DIR
Environment=PATH=$CURRENT_DIR/freeware_env/bin
ExecStart=$CURRENT_DIR/freeware_env/bin/python main_bot.py --mode daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        
        log_success "Systemd service created"
        log_info "To start the bot service: sudo systemctl start freeware-bot"
        log_info "To enable autostart: sudo systemctl enable freeware-bot"
    fi
}

# Print final instructions
print_instructions() {
    log_success "Installation completed successfully!"
    echo
    echo "🎉 Freeware Bot is now installed and ready to use!"
    echo
    echo "📝 Next steps:"
    echo "1. Edit .env file with your cloud storage credentials:"
    echo "   nano .env"
    echo
    echo "2. Configure rclone for cloud storage (optional):"
    echo "   rclone config"
    echo
    echo "3. Test the bot:"
    echo "   source freeware_env/bin/activate"
    echo "   python main_bot.py --mode status"
    echo
    echo "4. Run a test scrape:"
    echo "   python main_bot.py --mode scrape"
    echo
    echo "5. Start the bot daemon:"
    echo "   python main_bot.py --mode daemon"
    echo
    if [[ "$OS" != "macos" ]]; then
        echo "6. Or use systemd service:"
        echo "   sudo systemctl start freeware-bot"
        echo "   sudo systemctl enable freeware-bot"
        echo
    fi
    echo "📖 For more information, see README.md"
    echo "🐛 Report issues at: https://github.com/your-username/freeware-bot/issues"
}

# Main installation function
main() {
    echo "🚀 Freeware Bot Installer"
    echo "========================"
    echo
    
    check_root
    detect_os
    
    # Check if already installed
    if [[ -d "freeware_env" ]] && [[ -f ".env" ]]; then
        log_warning "Freeware Bot appears to be already installed."
        echo -n "Do you want to reinstall? [y/N]: "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Installation cancelled"
            exit 0
        fi
        log_info "Proceeding with reinstallation..."
        rm -rf freeware_env
    fi
    
    # Run installation steps
    install_system_dependencies
    setup_python_env
    create_directories
    setup_database
    setup_config
    setup_rclone
    test_installation
    create_service
    
    print_instructions
}

# Handle interruption
trap 'log_error "Installation interrupted"; exit 1' INT TERM

# Run main function
main "$@"