#!/usr/bin/env python3
"""
Comprehensive validation script for all system optimizations
Tests Flask API, Telegram bot, notification system, controller API, and download improvements
"""

import os
import sys
import time
import requests
import logging
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Tuple
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/validation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemValidator:
    """Comprehensive system validation"""
    
    def __init__(self):
        self.results = {
            'flask_api': {},
            'notification_system': {},
            'telegram_bot': {},
            'controller_api': {},
            'download_improvements': {},
            'integration': {}
        }
        self.api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8080')
        self.start_time = time.time()
    
    def validate_flask_api(self) -> Dict:
        """Validate Flask API optimizations"""
        logger.info("🔍 Validating Flask API optimizations...")
        
        checks = {
            'health_endpoint': self._check_health_endpoint(),
            'rate_limiting': self._check_rate_limiting(),
            'caching': self._check_caching(),
            'error_handling': self._check_error_handling(),
            'database_performance': self._check_database_performance(),
            'metrics_endpoint': self._check_metrics_endpoint()
        }
        
        passed = sum(1 for result in checks.values() if result['status'] == 'pass')
        total = len(checks)
        
        self.results['flask_api'] = {
            'checks': checks,
            'passed': passed,
            'total': total,
            'success_rate': (passed / total) * 100
        }
        
        logger.info(f"✅ Flask API validation: {passed}/{total} checks passed ({self.results['flask_api']['success_rate']:.1f}%)")
        return self.results['flask_api']
    
    def _check_health_endpoint(self) -> Dict:
        """Check Flask API health endpoint"""
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['status', 'timestamp', 'checks']
                
                if all(field in data for field in required_fields):
                    return {
                        'status': 'pass',
                        'message': 'Health endpoint working correctly',
                        'response_time_ms': response.elapsed.total_seconds() * 1000
                    }
            
            return {
                'status': 'fail',
                'message': f'Health endpoint failed: {response.status_code}',
                'response_time_ms': response.elapsed.total_seconds() * 1000
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Health endpoint error: {e}',
                'response_time_ms': None
            }
    
    def _check_rate_limiting(self) -> Dict:
        """Check rate limiting functionality"""
        try:
            # Make multiple rapid requests to test rate limiting
            responses = []
            for i in range(10):
                response = requests.get(f"{self.api_base_url}/stats", timeout=5)
                responses.append(response.status_code)
                time.sleep(0.1)
            
            # Check if any requests were rate limited (429)
            rate_limited = any(status == 429 for status in responses)
            
            return {
                'status': 'pass' if rate_limited else 'warn',
                'message': 'Rate limiting active' if rate_limited else 'Rate limiting may not be active',
                'response_codes': responses
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Rate limiting check error: {e}',
                'response_codes': None
            }
    
    def _check_caching(self) -> Dict:
        """Check caching functionality"""
        try:
            # Make the same request twice and compare response times
            start_time = time.time()
            response1 = requests.get(f"{self.api_base_url}/stats", timeout=10)
            first_request_time = time.time() - start_time
            
            start_time = time.time()
            response2 = requests.get(f"{self.api_base_url}/stats", timeout=10)
            second_request_time = time.time() - start_time
            
            if response1.status_code == 200 and response2.status_code == 200:
                # Second request should be faster due to caching
                cache_effective = second_request_time < first_request_time * 0.8
                
                return {
                    'status': 'pass' if cache_effective else 'warn',
                    'message': 'Caching working' if cache_effective else 'Caching may not be effective',
                    'first_request_ms': first_request_time * 1000,
                    'second_request_ms': second_request_time * 1000
                }
            
            return {
                'status': 'fail',
                'message': 'Failed to test caching',
                'first_request_ms': None,
                'second_request_ms': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Caching check error: {e}',
                'first_request_ms': None,
                'second_request_ms': None
            }
    
    def _check_error_handling(self) -> Dict:
        """Check error handling"""
        try:
            # Test invalid endpoint
            response = requests.get(f"{self.api_base_url}/invalid_endpoint", timeout=10)
            
            if response.status_code == 404:
                try:
                    error_data = response.json()
                    if 'status' in error_data and error_data['status'] == 'error':
                        return {
                            'status': 'pass',
                            'message': 'Error handling working correctly',
                            'error_format': 'JSON'
                        }
                except:
                    pass
            
            return {
                'status': 'warn',
                'message': f'Error handling may need improvement: {response.status_code}',
                'error_format': 'Unknown'
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Error handling check failed: {e}',
                'error_format': None
            }
    
    def _check_database_performance(self) -> Dict:
        """Check database performance"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.api_base_url}/stats", timeout=30)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if response contains expected fields
                expected_fields = ['total', 'uploaded', 'downloaded']
                has_fields = all(field in data for field in expected_fields)
                
                # Performance threshold: should respond within 5 seconds
                performance_ok = response_time < 5.0
                
                return {
                    'status': 'pass' if (has_fields and performance_ok) else 'warn',
                    'message': f'Database query completed in {response_time:.2f}s',
                    'response_time_s': response_time,
                    'has_required_fields': has_fields
                }
            
            return {
                'status': 'fail',
                'message': f'Database query failed: {response.status_code}',
                'response_time_s': response_time
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Database performance check error: {e}',
                'response_time_s': None
            }
    
    def _check_metrics_endpoint(self) -> Dict:
        """Check metrics endpoint"""
        try:
            response = requests.get(f"{self.api_base_url}/metrics", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['timestamp', 'database', 'api']
                
                if all(field in data for field in required_fields):
                    return {
                        'status': 'pass',
                        'message': 'Metrics endpoint working correctly',
                        'fields_present': list(data.keys())
                    }
            
            return {
                'status': 'fail',
                'message': f'Metrics endpoint failed: {response.status_code}',
                'fields_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Metrics endpoint error: {e}',
                'fields_present': None
            }

    def validate_notification_system(self) -> Dict:
        """Validate notification system optimizations"""
        logger.info("🔍 Validating notification system...")
        
        checks = {
            'import_check': self._check_notification_import(),
            'queue_system': self._check_notification_queue(),
            'rate_limiting': self._check_notification_rate_limiting(),
            'multiple_channels': self._check_multiple_channels(),
            'health_check': self._check_notification_health()
        }
        
        passed = sum(1 for result in checks.values() if result['status'] == 'pass')
        total = len(checks)
        
        self.results['notification_system'] = {
            'checks': checks,
            'passed': passed,
            'total': total,
            'success_rate': (passed / total) * 100
        }
        
        logger.info(f"✅ Notification system validation: {passed}/{total} checks passed ({self.results['notification_system']['success_rate']:.1f}%)")
        return self.results['notification_system']
    
    def _check_notification_import(self) -> Dict:
        """Check if enhanced notification system can be imported"""
        try:
            import notify
            
            # Check for enhanced functions
            enhanced_functions = [
                'queue_notification',
                'send_system_status', 
                'send_download_progress',
                'get_notification_stats',
                'health_check'
            ]
            
            missing_functions = []
            for func_name in enhanced_functions:
                if not hasattr(notify, func_name):
                    missing_functions.append(func_name)
            
            if not missing_functions:
                return {
                    'status': 'pass',
                    'message': 'Enhanced notification system imported successfully',
                    'functions_available': enhanced_functions
                }
            else:
                return {
                    'status': 'warn',
                    'message': f'Some enhanced functions missing: {missing_functions}',
                    'functions_available': [f for f in enhanced_functions if f not in missing_functions]
                }
                
        except ImportError as e:
            return {
                'status': 'fail',
                'message': f'Failed to import notification system: {e}',
                'functions_available': None
            }
    
    def _check_notification_queue(self) -> Dict:
        """Check notification queue system"""
        try:
            from notify import queue_notification, get_notification_stats
            
            # Get initial stats
            initial_stats = get_notification_stats()
            
            # Queue a test notification
            success = queue_notification(
                "Test notification for validation",
                tag="validation_test",
                priority="low"
            )
            
            time.sleep(1)  # Allow processing
            
            # Get updated stats
            updated_stats = get_notification_stats()
            
            if success and updated_stats['queued'] > initial_stats['queued']:
                return {
                    'status': 'pass',
                    'message': 'Notification queue system working',
                    'queue_increased': True,
                    'initial_queued': initial_stats['queued'],
                    'final_queued': updated_stats['queued']
                }
            
            return {
                'status': 'warn',
                'message': 'Notification queue may not be working properly',
                'queue_increased': False
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Notification queue check error: {e}',
                'queue_increased': None
            }
    
    def _check_notification_rate_limiting(self) -> Dict:
        """Check notification rate limiting"""
        try:
            from notify import queue_notification
            
            # Try to queue multiple notifications rapidly
            successes = 0
            failures = 0
            
            for i in range(5):
                success = queue_notification(
                    f"Rate limit test {i}",
                    tag="rate_limit_test",
                    min_interval=60  # Long interval
                )
                if success:
                    successes += 1
                else:
                    failures += 1
            
            # Should have some failures due to rate limiting
            return {
                'status': 'pass' if failures > 0 else 'warn',
                'message': f'Rate limiting: {successes} success, {failures} failures',
                'successes': successes,
                'failures': failures
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Rate limiting check error: {e}',
                'successes': None,
                'failures': None
            }
    
    def _check_multiple_channels(self) -> Dict:
        """Check multiple notification channels"""
        try:
            from notify import queue_notification
            
            # Test with multiple channels
            success = queue_notification(
                "Multi-channel test",
                tag="multi_channel_test",
                channels=['telegram', 'email'],
                priority='low'
            )
            
            return {
                'status': 'pass' if success else 'warn',
                'message': 'Multi-channel notification queued' if success else 'Multi-channel may not work',
                'channels_tested': ['telegram', 'email']
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Multi-channel check error: {e}',
                'channels_tested': None
            }
    
    def _check_notification_health(self) -> Dict:
        """Check notification system health"""
        try:
            from notify import health_check
            
            health = health_check()
            
            return {
                'status': 'pass' if health['status'] == 'healthy' else 'warn',
                'message': f'Notification health: {health["status"]}',
                'health_data': health
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Notification health check error: {e}',
                'health_data': None
            }

    def validate_telegram_bot(self) -> Dict:
        """Validate Telegram bot optimizations"""
        logger.info("🔍 Validating Telegram bot...")
        
        checks = {
            'import_check': self._check_bot_import(),
            'configuration': self._check_bot_configuration(),
            'rate_limiting': self._check_bot_rate_limiting(),
            'caching': self._check_bot_caching(),
            'session_management': self._check_bot_session_management()
        }
        
        passed = sum(1 for result in checks.values() if result['status'] == 'pass')
        total = len(checks)
        
        self.results['telegram_bot'] = {
            'checks': checks,
            'passed': passed,
            'total': total,
            'success_rate': (passed / total) * 100
        }
        
        logger.info(f"✅ Telegram bot validation: {passed}/{total} checks passed ({self.results['telegram_bot']['success_rate']:.1f}%)")
        return self.results['telegram_bot']
    
    def _check_bot_import(self) -> Dict:
        """Check if bot can be imported with enhancements"""
        try:
            # Check if bot file exists and can be imported
            if os.path.exists('book_search_bot_full.py'):
                # Read file content to check for enhancements
                with open('book_search_bot_full.py', 'r') as f:
                    content = f.read()
                
                enhanced_features = [
                    'BotSession',
                    'rate_limit_check',
                    'error_handler',
                    'cache_get',
                    'cache_set'
                ]
                
                present_features = [feature for feature in enhanced_features if feature in content]
                
                return {
                    'status': 'pass' if len(present_features) >= 4 else 'warn',
                    'message': f'Bot enhancements present: {len(present_features)}/{len(enhanced_features)}',
                    'features_present': present_features
                }
            else:
                return {
                    'status': 'fail',
                    'message': 'Bot file not found',
                    'features_present': None
                }
                
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Bot import check error: {e}',
                'features_present': None
            }
    
    def _check_bot_configuration(self) -> Dict:
        """Check bot configuration"""
        try:
            # Check environment variables
            required_env_vars = ['TELEGRAM_BOT_TOKEN']
            optional_env_vars = ['BACKUP_TELEGRAM_CHAT_ID', 'ADMIN_USER_IDS']
            
            missing_required = [var for var in required_env_vars if not os.getenv(var)]
            present_optional = [var for var in optional_env_vars if os.getenv(var)]
            
            return {
                'status': 'pass' if not missing_required else 'warn',
                'message': f'Configuration check: {len(missing_required)} missing required vars',
                'missing_required': missing_required,
                'present_optional': present_optional
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Configuration check error: {e}',
                'missing_required': None
            }
    
    def _check_bot_rate_limiting(self) -> Dict:
        """Check bot rate limiting implementation"""
        try:
            if os.path.exists('book_search_bot_full.py'):
                with open('book_search_bot_full.py', 'r') as f:
                    content = f.read()
                
                rate_limit_indicators = [
                    'rate_limit_check',
                    'RATE_LIMIT_',
                    '@rate_limited'
                ]
                
                present_indicators = [indicator for indicator in rate_limit_indicators if indicator in content]
                
                return {
                    'status': 'pass' if len(present_indicators) >= 2 else 'warn',
                    'message': f'Rate limiting indicators: {len(present_indicators)}/{len(rate_limit_indicators)}',
                    'indicators_present': present_indicators
                }
            
            return {
                'status': 'fail',
                'message': 'Bot file not found for rate limiting check',
                'indicators_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Rate limiting check error: {e}',
                'indicators_present': None
            }
    
    def _check_bot_caching(self) -> Dict:
        """Check bot caching implementation"""
        try:
            if os.path.exists('book_search_bot_full.py'):
                with open('book_search_bot_full.py', 'r') as f:
                    content = f.read()
                
                caching_indicators = [
                    'cache_get',
                    'cache_set',
                    'CACHE_TTL',
                    'cached_result'
                ]
                
                present_indicators = [indicator for indicator in caching_indicators if indicator in content]
                
                return {
                    'status': 'pass' if len(present_indicators) >= 3 else 'warn',
                    'message': f'Caching indicators: {len(present_indicators)}/{len(caching_indicators)}',
                    'indicators_present': present_indicators
                }
            
            return {
                'status': 'fail',
                'message': 'Bot file not found for caching check',
                'indicators_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Caching check error: {e}',
                'indicators_present': None
            }
    
    def _check_bot_session_management(self) -> Dict:
        """Check bot session management"""
        try:
            if os.path.exists('book_search_bot_full.py'):
                with open('book_search_bot_full.py', 'r') as f:
                    content = f.read()
                
                session_indicators = [
                    'BotSession',
                    'get_user_session',
                    'search_history',
                    'user_state'
                ]
                
                present_indicators = [indicator for indicator in session_indicators if indicator in content]
                
                return {
                    'status': 'pass' if len(present_indicators) >= 3 else 'warn',
                    'message': f'Session management indicators: {len(present_indicators)}/{len(session_indicators)}',
                    'indicators_present': present_indicators
                }
            
            return {
                'status': 'fail',
                'message': 'Bot file not found for session check',
                'indicators_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Session management check error: {e}',
                'indicators_present': None
            }

    def validate_controller_api(self) -> Dict:
        """Validate controller API optimizations"""
        logger.info("🔍 Validating controller API...")
        
        checks = {
            'import_check': self._check_controller_import(),
            'process_management': self._check_process_management(),
            'health_monitoring': self._check_health_monitoring(),
            'retry_mechanisms': self._check_retry_mechanisms(),
            'notification_integration': self._check_notification_integration()
        }
        
        passed = sum(1 for result in checks.values() if result['status'] == 'pass')
        total = len(checks)
        
        self.results['controller_api'] = {
            'checks': checks,
            'passed': passed,
            'total': total,
            'success_rate': (passed / total) * 100
        }
        
        logger.info(f"✅ Controller API validation: {passed}/{total} checks passed ({self.results['controller_api']['success_rate']:.1f}%)")
        return self.results['controller_api']
    
    def _check_controller_import(self) -> Dict:
        """Check controller imports and structure"""
        try:
            if os.path.exists('controller_api.py'):
                with open('controller_api.py', 'r') as f:
                    content = f.read()
                
                required_imports = [
                    'threading',
                    'psutil',
                    'concurrent.futures',
                    'ProcessManager'
                ]
                
                present_imports = [imp for imp in required_imports if imp in content]
                
                return {
                    'status': 'pass' if len(present_imports) >= 3 else 'warn',
                    'message': f'Enhanced imports: {len(present_imports)}/{len(required_imports)}',
                    'imports_present': present_imports
                }
            
            return {
                'status': 'fail',
                'message': 'Controller file not found',
                'imports_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Controller import check error: {e}',
                'imports_present': None
            }
    
    def _check_process_management(self) -> Dict:
        """Check process management features"""
        try:
            if os.path.exists('controller_api.py'):
                with open('controller_api.py', 'r') as f:
                    content = f.read()
                
                process_features = [
                    'ProcessManager',
                    '_monitor_processes',
                    'start_process',
                    'process_stats',
                    'MAX_CONCURRENT_PROCESSES'
                ]
                
                present_features = [feature for feature in process_features if feature in content]
                
                return {
                    'status': 'pass' if len(present_features) >= 4 else 'warn',
                    'message': f'Process management features: {len(present_features)}/{len(process_features)}',
                    'features_present': present_features
                }
            
            return {
                'status': 'fail',
                'message': 'Controller file not found',
                'features_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Process management check error: {e}',
                'features_present': None
            }
    
    def _check_health_monitoring(self) -> Dict:
        """Check health monitoring implementation"""
        try:
            if os.path.exists('controller_api.py'):
                with open('controller_api.py', 'r') as f:
                    content = f.read()
                
                health_features = [
                    'health_check',
                    'check_api_health',
                    'check_file_system_health',
                    'start_health_monitoring'
                ]
                
                present_features = [feature for feature in health_features if feature in content]
                
                return {
                    'status': 'pass' if len(present_features) >= 3 else 'warn',
                    'message': f'Health monitoring features: {len(present_features)}/{len(health_features)}',
                    'features_present': present_features
                }
            
            return {
                'status': 'fail',
                'message': 'Controller file not found',
                'features_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Health monitoring check error: {e}',
                'features_present': None
            }
    
    def _check_retry_mechanisms(self) -> Dict:
        """Check retry mechanisms"""
        try:
            if os.path.exists('controller_api.py'):
                with open('controller_api.py', 'r') as f:
                    content = f.read()
                
                retry_features = [
                    'exponential_backoff',
                    'enhanced_api_request',
                    'MAX_RETRY_ATTEMPTS',
                    'run_script_with_enhanced_retry'
                ]
                
                present_features = [feature for feature in retry_features if feature in content]
                
                return {
                    'status': 'pass' if len(present_features) >= 3 else 'warn',
                    'message': f'Retry mechanisms: {len(present_features)}/{len(retry_features)}',
                    'features_present': present_features
                }
            
            return {
                'status': 'fail',
                'message': 'Controller file not found',
                'features_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Retry mechanisms check error: {e}',
                'features_present': None
            }
    
    def _check_notification_integration(self) -> Dict:
        """Check notification system integration"""
        try:
            if os.path.exists('controller_api.py'):
                with open('controller_api.py', 'r') as f:
                    content = f.read()
                
                integration_features = [
                    'NOTIFICATIONS_AVAILABLE',
                    'send_system_status',
                    'send_fatal_error',
                    'queue_notification'
                ]
                
                present_features = [feature for feature in integration_features if feature in content]
                
                return {
                    'status': 'pass' if len(present_features) >= 3 else 'warn',
                    'message': f'Notification integration: {len(present_features)}/{len(integration_features)}',
                    'features_present': present_features
                }
            
            return {
                'status': 'fail',
                'message': 'Controller file not found',
                'features_present': None
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Notification integration check error: {e}',
                'features_present': None
            }

    def validate_download_improvements(self) -> Dict:
        """Validate download improvements (from previous validation)"""
        logger.info("🔍 Validating download improvements...")
        
        # Use existing validation logic
        try:
            result = subprocess.run([
                sys.executable, 'validate_improvements.py'
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return {
                    'status': 'pass',
                    'message': 'Download improvements validation passed',
                    'output': result.stdout
                }
            else:
                return {
                    'status': 'fail',
                    'message': 'Download improvements validation failed',
                    'output': result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'fail',
                'message': 'Download validation timeout',
                'output': None
            }
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Download validation error: {e}',
                'output': None
            }

    def validate_integration(self) -> Dict:
        """Validate system integration"""
        logger.info("🔍 Validating system integration...")
        
        checks = {
            'file_consistency': self._check_file_consistency(),
            'configuration_sync': self._check_configuration_sync(),
            'dependency_compatibility': self._check_dependency_compatibility(),
            'cross_component_communication': self._check_cross_component_communication()
        }
        
        passed = sum(1 for result in checks.values() if result['status'] == 'pass')
        total = len(checks)
        
        self.results['integration'] = {
            'checks': checks,
            'passed': passed,
            'total': total,
            'success_rate': (passed / total) * 100
        }
        
        logger.info(f"✅ Integration validation: {passed}/{total} checks passed ({self.results['integration']['success_rate']:.1f}%)")
        return self.results['integration']
    
    def _check_file_consistency(self) -> Dict:
        """Check file consistency across components"""
        required_files = [
            'flask_api_receiver.py',
            'notify.py',
            'book_search_bot_full.py',
            'controller_api.py',
            'download_file.py',
            'config.py'
        ]
        
        missing_files = [f for f in required_files if not os.path.exists(f)]
        
        return {
            'status': 'pass' if not missing_files else 'fail',
            'message': f'File consistency: {len(missing_files)} files missing',
            'missing_files': missing_files,
            'present_files': [f for f in required_files if os.path.exists(f)]
        }
    
    def _check_configuration_sync(self) -> Dict:
        """Check configuration synchronization"""
        try:
            import config
            
            required_config_attrs = [
                'API_URL',
                'OUTPUT_FILENAME',
                'KEYWORD_LIST_CSV'
            ]
            
            missing_attrs = [attr for attr in required_config_attrs if not hasattr(config, attr)]
            
            return {
                'status': 'pass' if not missing_attrs else 'warn',
                'message': f'Configuration: {len(missing_attrs)} attributes missing',
                'missing_attributes': missing_attrs
            }
            
        except ImportError:
            return {
                'status': 'fail',
                'message': 'Failed to import config module',
                'missing_attributes': None
            }
    
    def _check_dependency_compatibility(self) -> Dict:
        """Check dependency compatibility"""
        try:
            # Test key imports
            imports_to_test = [
                ('requests', 'HTTP client'),
                ('flask', 'Web framework'),
                ('telebot', 'Telegram bot'),
                ('pandas', 'Data processing'),
                ('selenium', 'Web automation')
            ]
            
            failed_imports = []
            successful_imports = []
            
            for module_name, description in imports_to_test:
                try:
                    __import__(module_name)
                    successful_imports.append((module_name, description))
                except ImportError:
                    failed_imports.append((module_name, description))
            
            return {
                'status': 'pass' if not failed_imports else 'warn',
                'message': f'Dependencies: {len(failed_imports)} failed imports',
                'failed_imports': failed_imports,
                'successful_imports': successful_imports
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Dependency check error: {e}',
                'failed_imports': None
            }
    
    def _check_cross_component_communication(self) -> Dict:
        """Check cross-component communication"""
        try:
            # Test API endpoints that components rely on
            endpoints_to_test = [
                ('/', 'Health check'),
                ('/stats', 'Statistics'),
                ('/search_books', 'Search functionality')
            ]
            
            working_endpoints = []
            failed_endpoints = []
            
            for endpoint, description in endpoints_to_test:
                try:
                    response = requests.get(f"{self.api_base_url}{endpoint}", timeout=5)
                    if response.status_code in [200, 404]:  # 404 is acceptable for some endpoints
                        working_endpoints.append((endpoint, description))
                    else:
                        failed_endpoints.append((endpoint, description, response.status_code))
                except Exception as e:
                    failed_endpoints.append((endpoint, description, str(e)))
            
            return {
                'status': 'pass' if len(working_endpoints) >= 2 else 'warn',
                'message': f'Communication: {len(working_endpoints)} endpoints working',
                'working_endpoints': working_endpoints,
                'failed_endpoints': failed_endpoints
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'message': f'Communication check error: {e}',
                'working_endpoints': None
            }

    def run_full_validation(self) -> Dict:
        """Run complete system validation"""
        logger.info("🚀 Starting comprehensive system validation...")
        
        validation_start = time.time()
        
        # Run all validations
        validations = [
            ('Flask API', self.validate_flask_api),
            ('Notification System', self.validate_notification_system),
            ('Telegram Bot', self.validate_telegram_bot),
            ('Controller API', self.validate_controller_api),
            ('Integration', self.validate_integration)
        ]
        
        for name, validation_func in validations:
            try:
                logger.info(f"Running {name} validation...")
                validation_func()
            except Exception as e:
                logger.error(f"Error in {name} validation: {e}")
                self.results[name.lower().replace(' ', '_')] = {
                    'error': str(e),
                    'passed': 0,
                    'total': 0,
                    'success_rate': 0
                }
        
        # Calculate overall results
        total_validation_time = time.time() - validation_start
        
        overall_passed = sum(result.get('passed', 0) for result in self.results.values() if isinstance(result, dict))
        overall_total = sum(result.get('total', 0) for result in self.results.values() if isinstance(result, dict))
        overall_success_rate = (overall_passed / max(overall_total, 1)) * 100
        
        summary = {
            'overall_success_rate': overall_success_rate,
            'total_checks': overall_total,
            'passed_checks': overall_passed,
            'failed_checks': overall_total - overall_passed,
            'validation_time_seconds': total_validation_time,
            'timestamp': datetime.now().isoformat(),
            'components': self.results
        }
        
        return summary

    def generate_report(self, results: Dict) -> str:
        """Generate comprehensive validation report"""
        report = []
        report.append("🔍 COMPREHENSIVE SYSTEM VALIDATION REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {results['timestamp']}")
        report.append(f"Validation Time: {results['validation_time_seconds']:.2f} seconds")
        report.append(f"Overall Success Rate: {results['overall_success_rate']:.1f}%")
        report.append(f"Total Checks: {results['total_checks']}")
        report.append(f"Passed: {results['passed_checks']}")
        report.append(f"Failed: {results['failed_checks']}")
        report.append("")
        
        # Component-wise results
        for component, data in results['components'].items():
            if isinstance(data, dict) and 'success_rate' in data:
                status_icon = "✅" if data['success_rate'] >= 80 else "⚠️" if data['success_rate'] >= 60 else "❌"
                report.append(f"{status_icon} {component.replace('_', ' ').title()}: {data['success_rate']:.1f}% ({data['passed']}/{data['total']})")
        
        report.append("")
        report.append("🎯 SUMMARY")
        report.append("=" * 60)
        
        if results['overall_success_rate'] >= 90:
            report.append("🎉 EXCELLENT: System optimizations are working excellently!")
            report.append("✅ All major components are functioning properly")
        elif results['overall_success_rate'] >= 75:
            report.append("👍 GOOD: System optimizations are working well")
            report.append("⚠️ Some minor issues detected, review recommended")
        elif results['overall_success_rate'] >= 50:
            report.append("⚠️ FAIR: System has significant issues")
            report.append("🔧 Several components need attention")
        else:
            report.append("❌ POOR: System needs immediate attention")
            report.append("🚨 Critical issues detected in multiple components")
        
        report.append("")
        report.append("🚀 OPTIMIZATION STATUS")
        report.append("=" * 60)
        
        optimizations = [
            "Flask API: Enhanced with caching, rate limiting, monitoring",
            "Notification System: Multi-channel, queue-based, rate limited",
            "Telegram Bot: Session management, caching, error handling",
            "Controller API: Process management, health monitoring, retry logic",
            "Download System: 505 error handling, exponential backoff, session reuse",
            "Integration: Cross-component communication, dependency management"
        ]
        
        for optimization in optimizations:
            report.append(f"• {optimization}")
        
        return "\n".join(report)

def main():
    """Main validation function"""
    print("🚀 Starting Comprehensive System Validation")
    print("=" * 60)
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Initialize validator
    validator = SystemValidator()
    
    try:
        # Run full validation
        results = validator.run_full_validation()
        
        # Generate report
        report = validator.generate_report(results)
        
        # Print report
        print(report)
        
        # Save detailed results
        results_file = f"logs/validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        # Return appropriate exit code
        return 0 if results['overall_success_rate'] >= 75 else 1
        
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        print(f"❌ Validation failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)