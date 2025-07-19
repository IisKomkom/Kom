import os
import subprocess
import logging
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import requests
from config import RCLONE_CONFIG, MEDIAFIRE_CONFIG, MEGA_CONFIG, GDRIVE_CONFIG

class CloudUploader:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rclone_config = RCLONE_CONFIG['config_file']
        self.setup_rclone_config()
        
    def setup_rclone_config(self):
        """Setup rclone configuration if not exists"""
        config_path = Path(self.rclone_config).expanduser()
        config_dir = config_path.parent
        
        # Create config directory if not exists
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if rclone is installed
        if not self.check_rclone_installed():
            self.logger.error("rclone is not installed or not in PATH")
            return False
        
        # Generate config if not exists
        if not config_path.exists():
            self.generate_rclone_config()
        
        return True
    
    def check_rclone_installed(self) -> bool:
        """Check if rclone is installed"""
        try:
            result = subprocess.run(['rclone', 'version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def generate_rclone_config(self):
        """Generate basic rclone configuration"""
        try:
            config_content = self._build_config_content()
            config_path = Path(self.rclone_config).expanduser()
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            self.logger.info(f"Generated rclone config at {config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to generate rclone config: {e}")
    
    def _build_config_content(self) -> str:
        """Build rclone configuration content"""
        config_sections = []
        
        # MediaFire configuration
        if MEDIAFIRE_CONFIG.get('email') and MEDIAFIRE_CONFIG.get('password'):
            config_sections.append(f"""
[mediafire]
type = mediafire
user = {MEDIAFIRE_CONFIG['email']}
pass = {self._obscure_password(MEDIAFIRE_CONFIG['password'])}
""")
        
        # MEGA configuration  
        if MEGA_CONFIG.get('email') and MEGA_CONFIG.get('password'):
            config_sections.append(f"""
[mega]
type = mega
user = {MEGA_CONFIG['email']}
pass = {self._obscure_password(MEGA_CONFIG['password'])}
""")
        
        # Google Drive configuration
        if GDRIVE_CONFIG.get('service_account_file'):
            config_sections.append(f"""
[gdrive]
type = drive
service_account_file = {GDRIVE_CONFIG['service_account_file']}
""")
        
        return '\n'.join(config_sections)
    
    def _obscure_password(self, password: str) -> str:
        """Obscure password for rclone config"""
        try:
            result = subprocess.run(['rclone', 'obscure', password], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        return password  # Return plain password if obscure fails
    
    def upload_file(self, file_path: str, cloud_provider: str, remote_path: str = None) -> Dict[str, Any]:
        """Upload file to specified cloud provider"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return {'success': False, 'error': 'File not found'}
            
            # Determine remote name
            remote_name = self._get_remote_name(cloud_provider)
            if not remote_name:
                return {'success': False, 'error': f'Unsupported cloud provider: {cloud_provider}'}
            
            # Determine remote path
            if not remote_path:
                remote_path = f"freeware_bot/{file_path.name}"
            
            # Upload file
            upload_result = self._upload_with_rclone(file_path, remote_name, remote_path)
            
            if upload_result['success']:
                # Get share link
                share_link = self.get_share_link(cloud_provider, remote_path)
                upload_result['share_link'] = share_link
                
                self.logger.info(f"Successfully uploaded {file_path.name} to {cloud_provider}")
            
            return upload_result
            
        except Exception as e:
            self.logger.error(f"Error uploading file {file_path}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_remote_name(self, cloud_provider: str) -> Optional[str]:
        """Get rclone remote name for cloud provider"""
        mapping = {
            'mediafire': 'mediafire',
            'mega': 'mega', 
            'gdrive': 'gdrive'
        }
        return mapping.get(cloud_provider.lower())
    
    def _upload_with_rclone(self, file_path: Path, remote_name: str, remote_path: str) -> Dict[str, Any]:
        """Upload file using rclone"""
        try:
            start_time = time.time()
            
            # Build rclone command
            cmd = [
                'rclone', 'copy',
                str(file_path),
                f"{remote_name}:{remote_path}",
                '--progress',
                '--transfers', '1',
                '--checkers', '1',
                '--retries', '3',
                '--low-level-retries', '3'
            ]
            
            # Run rclone upload
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            upload_time = time.time() - start_time
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'upload_time': upload_time,
                    'remote_path': remote_path,
                    'output': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr,
                    'output': result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Upload timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_share_link(self, cloud_provider: str, remote_path: str) -> Optional[str]:
        """Get shareable link for uploaded file"""
        try:
            remote_name = self._get_remote_name(cloud_provider)
            
            # Try to get public link using rclone
            cmd = ['rclone', 'link', f"{remote_name}:{remote_path}"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Provider-specific link generation
            if cloud_provider.lower() == 'gdrive':
                return self._get_gdrive_share_link(remote_path)
            elif cloud_provider.lower() == 'mega':
                return self._get_mega_share_link(remote_path)
            elif cloud_provider.lower() == 'mediafire':
                return self._get_mediafire_share_link(remote_path)
            
        except Exception as e:
            self.logger.error(f"Error getting share link: {e}")
        
        return None
    
    def _get_gdrive_share_link(self, remote_path: str) -> Optional[str]:
        """Get Google Drive share link"""
        try:
            # Use rclone to get file ID
            cmd = ['rclone', 'lsjson', f"gdrive:{remote_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                files = json.loads(result.stdout)
                if files:
                    file_id = files[0].get('ID')
                    if file_id:
                        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
            
        except Exception as e:
            self.logger.error(f"Error getting Google Drive link: {e}")
        
        return None
    
    def _get_mega_share_link(self, remote_path: str) -> Optional[str]:
        """Get MEGA share link"""
        # MEGA links need to be generated through their API
        # This is a placeholder - implement actual MEGA API integration
        return None
    
    def _get_mediafire_share_link(self, remote_path: str) -> Optional[str]:
        """Get MediaFire share link"""
        # MediaFire links need to be generated through their API
        # This is a placeholder - implement actual MediaFire API integration
        return None
    
    def upload_multiple(self, file_paths: List[str], cloud_providers: List[str] = None) -> List[Dict[str, Any]]:
        """Upload multiple files to multiple cloud providers"""
        if not cloud_providers:
            cloud_providers = ['mediafire', 'mega', 'gdrive']
        
        results = []
        
        for file_path in file_paths:
            file_results = {'file_path': file_path, 'uploads': []}
            
            for provider in cloud_providers:
                upload_result = self.upload_file(file_path, provider)
                upload_result['provider'] = provider
                file_results['uploads'].append(upload_result)
                
                # Add delay between uploads
                time.sleep(2)
            
            results.append(file_results)
        
        return results
    
    def check_remote_exists(self, cloud_provider: str, remote_path: str) -> bool:
        """Check if file exists on remote"""
        try:
            remote_name = self._get_remote_name(cloud_provider)
            cmd = ['rclone', 'lsl', f"{remote_name}:{remote_path}"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Error checking remote file: {e}")
            return False
    
    def list_remote_files(self, cloud_provider: str, remote_path: str = "") -> List[Dict[str, Any]]:
        """List files on remote"""
        try:
            remote_name = self._get_remote_name(cloud_provider)
            cmd = ['rclone', 'lsjson', f"{remote_name}:{remote_path}"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            
        except Exception as e:
            self.logger.error(f"Error listing remote files: {e}")
        
        return []
    
    def delete_remote_file(self, cloud_provider: str, remote_path: str) -> bool:
        """Delete file from remote"""
        try:
            remote_name = self._get_remote_name(cloud_provider)
            cmd = ['rclone', 'delete', f"{remote_name}:{remote_path}"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Error deleting remote file: {e}")
            return False
    
    def get_remote_size(self, cloud_provider: str, remote_path: str = "") -> Dict[str, Any]:
        """Get remote storage usage"""
        try:
            remote_name = self._get_remote_name(cloud_provider)
            cmd = ['rclone', 'size', f"{remote_name}:{remote_path}", '--json']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            
        except Exception as e:
            self.logger.error(f"Error getting remote size: {e}")
        
        return {}
    
    def sync_folder(self, local_folder: str, cloud_provider: str, remote_folder: str = "") -> Dict[str, Any]:
        """Sync entire folder to cloud"""
        try:
            start_time = time.time()
            
            remote_name = self._get_remote_name(cloud_provider)
            cmd = [
                'rclone', 'sync',
                local_folder,
                f"{remote_name}:{remote_folder}",
                '--progress',
                '--transfers', '2',
                '--checkers', '2'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            
            sync_time = time.time() - start_time
            
            return {
                'success': result.returncode == 0,
                'sync_time': sync_time,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None
            }
            
        except Exception as e:
            self.logger.error(f"Error syncing folder: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_upload_stats(self) -> Dict[str, Any]:
        """Get upload statistics across all providers"""
        stats = {
            'providers': {},
            'total_files': 0,
            'total_size': 0
        }
        
        for provider in ['mediafire', 'mega', 'gdrive']:
            try:
                remote_files = self.list_remote_files(provider, 'freeware_bot')
                provider_stats = {
                    'file_count': len(remote_files),
                    'total_size': sum(f.get('Size', 0) for f in remote_files),
                    'files': remote_files
                }
                stats['providers'][provider] = provider_stats
                stats['total_files'] += provider_stats['file_count']
                stats['total_size'] += provider_stats['total_size']
                
            except Exception as e:
                self.logger.error(f"Error getting stats for {provider}: {e}")
                stats['providers'][provider] = {'error': str(e)}
        
        return stats

# Initialize uploader
cloud_uploader = CloudUploader()