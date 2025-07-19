import subprocess
import logging
import sys
import os
import time
from datetime import datetime, timedelta
import csv
import requests
import config
import pandas as pd
import threading
from queue import Queue, Empty
import psutil
import json
import signal
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

# Import enhanced notification system
try:
    from notify import send_system_status, send_fatal_error, send_batch_summary, queue_notification, get_notification_stats
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    logging.warning("Enhanced notification system not available")

# Enhanced Configuration
MAX_CONCURRENT_PROCESSES = int(os.getenv('MAX_CONCURRENT_PROCESSES', '3'))
PROCESS_TIMEOUT = int(os.getenv('PROCESS_TIMEOUT', '3600'))  # 1 hour
RETRY_DELAY_BASE = int(os.getenv('RETRY_DELAY_BASE', '5'))
MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '3'))
HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', '60'))  # 1 minute
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '10'))
API_TIMEOUT = int(os.getenv('API_TIMEOUT', '30'))

# Process Management
running_processes = {}
process_queue = Queue()
process_stats = {
    'total_started': 0,
    'total_completed': 0,
    'total_failed': 0,
    'current_running': 0,
    'start_time': datetime.now()
}

# Thread locks
stats_lock = threading.Lock()
process_lock = threading.Lock()

class ProcessManager:
    """Enhanced process management with monitoring and recovery"""
    
    def __init__(self):
        self.processes = {}
        self.executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_PROCESSES)
        self.monitoring_thread = None
        self.start_monitoring()
    
    def start_monitoring(self):
        """Start process monitoring thread"""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=self._monitor_processes, daemon=True)
            self.monitoring_thread.start()
            logging.info("✅ Process monitoring thread started")
    
    def _monitor_processes(self):
        """Monitor running processes and handle failures"""
        while True:
            try:
                current_time = datetime.now()
                
                with process_lock:
                    for proc_id, proc_info in list(self.processes.items()):
                        process = proc_info['process']
                        start_time = proc_info['start_time']
                        
                        # Check if process is still running
                        if process.poll() is not None:
                            # Process has finished
                            end_time = datetime.now()
                            duration = (end_time - start_time).total_seconds()
                            
                            if process.returncode == 0:
                                logging.info(f"✅ Process {proc_id} completed successfully in {duration:.2f}s")
                                with stats_lock:
                                    process_stats['total_completed'] += 1
                                    process_stats['current_running'] -= 1
                            else:
                                logging.error(f"❌ Process {proc_id} failed with code {process.returncode}")
                                with stats_lock:
                                    process_stats['total_failed'] += 1
                                    process_stats['current_running'] -= 1
                                
                                if NOTIFICATIONS_AVAILABLE:
                                    send_fatal_error(
                                        f"Process {proc_id} failed with exit code {process.returncode}",
                                        context="controller_api.py"
                                    )
                            
                            # Remove from tracking
                            del self.processes[proc_id]
                        
                        # Check for timeout
                        elif (current_time - start_time).total_seconds() > PROCESS_TIMEOUT:
                            logging.warning(f"⏰ Process {proc_id} timeout, terminating...")
                            self._terminate_process(process, proc_id)
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logging.error(f"Error in process monitoring: {e}")
                time.sleep(30)
    
    def _terminate_process(self, process: subprocess.Popen, proc_id: str):
        """Safely terminate a process"""
        try:
            # Try graceful termination first
            process.terminate()
            time.sleep(5)
            
            # Force kill if still running
            if process.poll() is None:
                process.kill()
                logging.warning(f"🔪 Force killed process {proc_id}")
            
            with stats_lock:
                process_stats['total_failed'] += 1
                process_stats['current_running'] -= 1
            
            if NOTIFICATIONS_AVAILABLE:
                send_fatal_error(f"Process {proc_id} terminated due to timeout", context="controller_api.py")
                
        except Exception as e:
            logging.error(f"Error terminating process {proc_id}: {e}")
    
    def start_process(self, script_name: str, log_path: str, context: Dict = None) -> Optional[str]:
        """Start a new process with enhanced monitoring"""
        if len(self.processes) >= MAX_CONCURRENT_PROCESSES:
            logging.warning(f"Maximum concurrent processes ({MAX_CONCURRENT_PROCESSES}) reached")
            return None
        
        proc_id = f"{script_name}_{int(time.time())}"
        
        try:
            with open(log_path, 'a', encoding='utf-8') as logf:
                process = subprocess.Popen(
                    [sys.executable, script_name],
                    stdout=logf,
                    stderr=logf,
                    env=os.environ.copy()
                )
            
            with process_lock:
                self.processes[proc_id] = {
                    'process': process,
                    'script_name': script_name,
                    'start_time': datetime.now(),
                    'context': context or {}
                }
            
            with stats_lock:
                process_stats['total_started'] += 1
                process_stats['current_running'] += 1
            
            logging.info(f"🚀 Started process {proc_id} for {script_name}")
            return proc_id
            
        except Exception as e:
            logging.error(f"Failed to start process {script_name}: {e}")
            if NOTIFICATIONS_AVAILABLE:
                send_fatal_error(f"Failed to start {script_name}: {e}", context="controller_api.py")
            return None
    
    def wait_for_process(self, proc_id: str, timeout: int = None) -> bool:
        """Wait for a specific process to complete"""
        if proc_id not in self.processes:
            return False
        
        process = self.processes[proc_id]['process']
        start_time = time.time()
        
        while process.poll() is None:
            if timeout and (time.time() - start_time) > timeout:
                logging.warning(f"Timeout waiting for process {proc_id}")
                return False
            time.sleep(1)
        
        return process.returncode == 0
    
    def get_process_status(self) -> Dict:
        """Get current process status"""
        with process_lock:
            running_processes = []
            for proc_id, proc_info in self.processes.items():
                running_processes.append({
                    'id': proc_id,
                    'script': proc_info['script_name'],
                    'start_time': proc_info['start_time'].isoformat(),
                    'duration': (datetime.now() - proc_info['start_time']).total_seconds(),
                    'pid': proc_info['process'].pid
                })
        
        with stats_lock:
            stats = process_stats.copy()
        
        return {
            'running_processes': running_processes,
            'stats': stats,
            'system_resources': self._get_system_resources()
        }
    
    def _get_system_resources(self) -> Dict:
        """Get current system resource usage"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
        except Exception as e:
            logging.error(f"Error getting system resources: {e}")
            return {}

# Initialize process manager
process_manager = ProcessManager()

def setup_logging():
    """Enhanced logging setup with rotation"""
    os.makedirs("log", exist_ok=True)
    log_file = datetime.now().strftime("log/log_controller_%Y-%m-%d_%H-%M-%S.txt")
    
    # Setup file handler with rotation
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            file_handler,
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.info("🚀 Enhanced Controller API started with monitoring")
    
    # Log system info
    logging.info(f"📊 System Info:")
    logging.info(f"  - CPU Cores: {psutil.cpu_count()}")
    logging.info(f"  - Memory: {psutil.virtual_memory().total / (1024**3):.2f} GB")
    logging.info(f"  - Python: {sys.version}")
    
    return log_file

def exponential_backoff(attempt: int, base_delay: int = RETRY_DELAY_BASE) -> int:
    """Calculate exponential backoff delay"""
    return min(base_delay * (2 ** attempt), 300)  # Max 5 minutes

def run_script_with_enhanced_retry(script_name: str, log_path: str, context: Dict = None) -> bool:
    """Enhanced script execution with retry logic and monitoring"""
    for attempt in range(MAX_RETRY_ATTEMPTS):
        logging.info(f"🔄 Running {script_name} - Attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}")
        
        # Start process
        proc_id = process_manager.start_process(script_name, log_path, context)
        if not proc_id:
            logging.error(f"Failed to start {script_name}")
            continue
        
        # Wait for completion
        success = process_manager.wait_for_process(proc_id, timeout=PROCESS_TIMEOUT)
        
        if success:
            logging.info(f"✅ {script_name} completed successfully")
            return True
        else:
            logging.warning(f"❌ {script_name} failed on attempt {attempt + 1}")
            
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                delay = exponential_backoff(attempt)
                logging.info(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
    
    logging.error(f"❌ {script_name} failed after {MAX_RETRY_ATTEMPTS} attempts")
    return False

def enhanced_api_request(url: str, data: Dict, timeout: int = API_TIMEOUT, retries: int = 3) -> bool:
    """Enhanced API request with retry logic"""
    for attempt in range(retries):
        try:
            response = requests.post(url, json=data, timeout=timeout)
            
            if response.status_code in [200, 201]:
                logging.info(f"✅ API request successful: {len(data)} items")
                return True
            elif response.status_code == 429:  # Rate limited
                retry_after = int(response.headers.get('Retry-After', 60))
                logging.warning(f"⏳ Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
            elif response.status_code >= 500:  # Server error
                delay = exponential_backoff(attempt)
                logging.warning(f"🔄 Server error {response.status_code}, retrying in {delay}s")
                time.sleep(delay)
            else:
                logging.error(f"❌ API error: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logging.warning(f"⏰ API timeout on attempt {attempt + 1}")
            if attempt < retries - 1:
                time.sleep(exponential_backoff(attempt))
        except Exception as e:
            logging.error(f"🔥 API exception on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                time.sleep(exponential_backoff(attempt))
    
    return False

def send_data_from_csv_enhanced(csv_file: str, api_url: str) -> bool:
    """Enhanced CSV data sending with batch processing and monitoring"""
    try:
        if not os.path.exists(csv_file):
            logging.error(f"CSV file not found: {csv_file}")
            return False
        
        df = pd.read_csv(csv_file)
        df = df.where(pd.notnull(df), None)
        
        # Validate data
        if df.empty:
            logging.warning(f"CSV file is empty: {csv_file}")
            return True
        
        total_rows = len(df)
        batch_count = 0
        success_count = 0
        failed_count = 0
        
        logging.info(f"📊 Processing {total_rows} rows from {csv_file}")
        
        # Process in batches
        for start_idx in range(0, total_rows, BATCH_SIZE):
            end_idx = min(start_idx + BATCH_SIZE, total_rows)
            batch = []
            
            for _, row in df.iloc[start_idx:end_idx].iterrows():
                # Validate row data
                id_val = row.get('id') or row.get('\ufeffid')
                if not id_val or not str(id_val).strip():
                    logging.warning(f"Skipping row without ID: {row.to_dict()}")
                    continue
                
                row_dict = row.to_dict()
                row_dict['id'] = str(id_val).strip()
                
                # Remove BOM column if exists
                if '\ufeffid' in row_dict:
                    del row_dict['\ufeffid']
                
                batch.append(row_dict)
            
            if batch:
                batch_count += 1
                logging.info(f"📤 Sending batch {batch_count} ({len(batch)} items)")
                
                if enhanced_api_request(api_url, batch):
                    success_count += len(batch)
                    logging.info(f"✅ Batch {batch_count} sent successfully")
                else:
                    failed_count += len(batch)
                    logging.error(f"❌ Batch {batch_count} failed")
                
                # Rate limiting between batches
                time.sleep(1)
        
        # Send summary notification
        if NOTIFICATIONS_AVAILABLE:
            send_batch_summary(
                success_count, 
                failed_count, 
                batch_type='API Upload',
                details={
                    'Total Rows': total_rows,
                    'Batches Sent': batch_count,
                    'File': os.path.basename(csv_file)
                }
            )
        
        logging.info(f"📊 CSV processing complete: {success_count} success, {failed_count} failed")
        return failed_count == 0
        
    except Exception as e:
        logging.error(f"🔥 Error processing CSV {csv_file}: {e}")
        if NOTIFICATIONS_AVAILABLE:
            send_fatal_error(f"CSV processing failed: {e}", context="controller_api.py")
        return False

def mark_keyword_done_enhanced(keyword_file: str, keyword_to_mark: str) -> bool:
    """Enhanced keyword marking with backup and validation"""
    try:
        if not os.path.exists(keyword_file):
            logging.error(f"Keyword file not found: {keyword_file}")
            return False
        
        # Create backup
        backup_file = f"{keyword_file}.backup_{int(time.time())}"
        import shutil
        shutil.copy2(keyword_file, backup_file)
        
        updated = []
        keyword_found = False
        
        with open(keyword_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('input') == keyword_to_mark:
                    row['status'] = 'done'
                    row['completed_at'] = datetime.now().isoformat()
                    keyword_found = True
                updated.append(row)
        
        if not keyword_found:
            logging.warning(f"Keyword '{keyword_to_mark}' not found in {keyword_file}")
            return False
        
        # Write updated data
        with open(keyword_file, 'w', newline='', encoding='utf-8') as f:
            if updated:
                writer = csv.DictWriter(f, fieldnames=updated[0].keys())
                writer.writeheader()
                writer.writerows(updated)
        
        logging.info(f"✅ Keyword '{keyword_to_mark}' marked as done")
        return True
        
    except Exception as e:
        logging.error(f"🔥 Error updating keyword file: {e}")
        return False

def process_keyword_enhanced(keyword: str, log_path: str) -> bool:
    """Enhanced keyword processing with comprehensive monitoring"""
    logging.info(f"🚀 Starting enhanced processing for keyword: '{keyword}'")
    
    start_time = time.time()
    steps = [
        ('scrape.py', 'Scraping'),
        ('deduplicate.py', 'Deduplication'), 
        ('download_coverc.py', 'Cover Download')
    ]
    
    for script, description in steps:
        logging.info(f"📋 Step: {description}")
        
        if not run_script_with_enhanced_retry(script, log_path, {'keyword': keyword, 'step': description}):
            logging.error(f"❌ Failed at step: {description}")
            
            if NOTIFICATIONS_AVAILABLE:
                send_fatal_error(
                    f"Keyword processing failed at {description} step", 
                    context=f"controller_api.py - keyword: {keyword}"
                )
            return False
    
    # Send data to API
    logging.info(f"📤 Uploading data to API")
    if not send_data_from_csv_enhanced(config.OUTPUT_FILENAME, config.API_URL):
        logging.error(f"❌ Failed to upload data to API")
        return False
    
    # Mark keyword as done
    if not mark_keyword_done_enhanced(config.KEYWORD_LIST_CSV, keyword):
        logging.error(f"❌ Failed to mark keyword as done")
        return False
    
    total_time = time.time() - start_time
    logging.info(f"✅ Keyword '{keyword}' processing completed in {total_time:.2f}s")
    
    if NOTIFICATIONS_AVAILABLE:
        send_batch_summary(
            1, 0, 
            batch_type=f'Keyword Processing',
            extra=f"Keyword: {keyword}",
            details={
                'Processing Time': f"{total_time:.2f}s",
                'Steps Completed': len(steps),
                'Keyword': keyword
            }
        )
    
    return True

def health_check() -> Dict:
    """Comprehensive system health check"""
    health = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'process_manager': process_manager.get_process_status(),
        'api_connectivity': check_api_health(),
        'file_system': check_file_system_health(),
        'notifications': get_notification_stats() if NOTIFICATIONS_AVAILABLE else None
    }
    
    # Determine overall health
    if health['process_manager']['stats']['current_running'] > MAX_CONCURRENT_PROCESSES:
        health['status'] = 'warning'
    
    if not health['api_connectivity']['healthy']:
        health['status'] = 'critical'
    
    return health

def check_api_health() -> Dict:
    """Check API endpoint health"""
    try:
        response = requests.get(f"{config.API_URL.replace('/upload_data', '/health')}", timeout=10)
        return {
            'healthy': response.status_code == 200,
            'response_time_ms': response.elapsed.total_seconds() * 1000,
            'status_code': response.status_code
        }
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e),
            'response_time_ms': None,
            'status_code': None
        }

def check_file_system_health() -> Dict:
    """Check file system health"""
    try:
        required_files = [config.KEYWORD_LIST_CSV, config.OUTPUT_FILENAME]
        missing_files = [f for f in required_files if not os.path.exists(f)]
        
        return {
            'all_files_present': len(missing_files) == 0,
            'missing_files': missing_files,
            'disk_space_gb': psutil.disk_usage('/').free / (1024**3)
        }
    except Exception as e:
        return {
            'all_files_present': False,
            'error': str(e),
            'disk_space_gb': None
        }

def start_health_monitoring():
    """Start health monitoring thread"""
    def monitor_health():
        while True:
            try:
                health = health_check()
                
                if health['status'] != 'healthy' and NOTIFICATIONS_AVAILABLE:
                    send_system_status(health, component='controller_api')
                
                time.sleep(HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                logging.error(f"Health monitoring error: {e}")
                time.sleep(HEALTH_CHECK_INTERVAL)
    
    health_thread = threading.Thread(target=monitor_health, daemon=True)
    health_thread.start()
    logging.info("🔍 Health monitoring started")

def graceful_shutdown(signum, frame):
    """Handle graceful shutdown"""
    logging.info("🛑 Graceful shutdown initiated...")
    
    # Stop all running processes
    with process_lock:
        for proc_id, proc_info in process_manager.processes.items():
            logging.info(f"🛑 Stopping process {proc_id}")
            process_manager._terminate_process(proc_info['process'], proc_id)
    
    if NOTIFICATIONS_AVAILABLE:
        queue_notification(
            "🛑 Controller API shutdown completed",
            tag='system_shutdown',
            priority='normal'
        )
    
    logging.info("👋 Controller API shutdown complete")
    sys.exit(0)

def main():
    """Enhanced main function with comprehensive error handling"""
    log_path = setup_logging()
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    # Start health monitoring
    start_health_monitoring()
    
    if NOTIFICATIONS_AVAILABLE:
        queue_notification(
            "🚀 Enhanced Controller API started successfully",
            tag='system_startup',
            priority='low'
        )
    
    try:
        # Check initial health
        initial_health = health_check()
        if initial_health['status'] == 'critical':
            logging.error("❌ Critical health issues detected, aborting")
            return
        
        # Main processing loop
        keywords_processed = 0
        start_time = time.time()
        
        with open(config.KEYWORD_LIST_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            total_keywords = sum(1 for row in reader if row.get('status', '').strip().lower() != 'done')
        
        logging.info(f"📋 Found {total_keywords} keywords to process")
        
        with open(config.KEYWORD_LIST_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                if row.get('status', '').strip().lower() != 'done':
                    keyword = row.get('input', '').strip()
                    if not keyword:
                        continue
                    
                    logging.info(f"🔄 Processing keyword {keywords_processed + 1}/{total_keywords}: '{keyword}'")
                    
                    if process_keyword_enhanced(keyword, log_path):
                        keywords_processed += 1
                        logging.info(f"✅ Keyword '{keyword}' completed ({keywords_processed}/{total_keywords})")
                    else:
                        logging.error(f"❌ Keyword '{keyword}' failed")
                    
                    # Health check between keywords
                    health = health_check()
                    if health['status'] == 'critical':
                        logging.error("❌ Critical health issues detected, stopping")
                        break
        
        total_time = time.time() - start_time
        logging.info(f"🎉 All processing completed: {keywords_processed} keywords in {total_time:.2f}s")
        
        if NOTIFICATIONS_AVAILABLE:
            send_batch_summary(
                keywords_processed,
                total_keywords - keywords_processed,
                batch_type='Complete Pipeline',
                details={
                    'Total Time': f"{total_time:.2f}s",
                    'Keywords Processed': keywords_processed,
                    'Average Time per Keyword': f"{total_time/max(keywords_processed, 1):.2f}s"
                }
            )
        
    except KeyboardInterrupt:
        logging.info("👤 Process interrupted by user")
    except Exception as e:
        logging.error(f"🔥 Fatal error in main process: {e}", exc_info=True)
        if NOTIFICATIONS_AVAILABLE:
            send_fatal_error(f"Fatal error in controller: {e}", context="controller_api.py")
    finally:
        # Final health report
        final_health = health_check()
        final_stats = process_manager.get_process_status()
        
        logging.info("📊 Final Statistics:")
        logging.info(f"  - Processes Started: {final_stats['stats']['total_started']}")
        logging.info(f"  - Processes Completed: {final_stats['stats']['total_completed']}")
        logging.info(f"  - Processes Failed: {final_stats['stats']['total_failed']}")
        logging.info(f"  - Final Health: {final_health['status']}")

if __name__ == "__main__":
    main()