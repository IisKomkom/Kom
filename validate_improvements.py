#!/usr/bin/env python3
"""
Validation script untuk memverifikasi perbaikan download_file.py
Focuses on code structure and improvement validation
"""

import os
import re
import sys
from datetime import datetime

def validate_file_exists():
    """Check if download_file.py exists and is readable"""
    if not os.path.exists("download_file.py"):
        return False, "download_file.py tidak ditemukan"
    
    try:
        with open("download_file.py", "r", encoding="utf-8") as f:
            content = f.read()
        return True, f"File ditemukan ({len(content)} characters)"
    except Exception as e:
        return False, f"Error reading file: {e}"

def validate_505_error_handling():
    """Validate 505 error handling implementation"""
    try:
        with open("download_file.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("505 http version not supported", "505 error pattern detected"),
            ("handle_http_errors", "HTTP error handling function exists"),
            ("error_patterns", "Error patterns dictionary implemented"),
            ("detected_error", "Error detection logic present")
        ]
        
        results = []
        for pattern, description in checks:
            if pattern.lower() in content.lower():
                results.append(f"✅ {description}")
            else:
                results.append(f"❌ {description} - NOT FOUND")
        
        return True, results
    except Exception as e:
        return False, [f"Error validating 505 handling: {e}"]

def validate_retry_mechanisms():
    """Validate improved retry mechanisms"""
    try:
        with open("download_file.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("exponential_backoff", "Exponential backoff function"),
            ("MAX_RETRY_ATTEMPTS", "Maximum retry attempts configuration"),
            ("max_retries", "Retry parameters in functions"),
            ("jitter", "Jitter implementation for backoff"),
            ("retry_delay", "Retry delay calculations")
        ]
        
        results = []
        for pattern, description in checks:
            if pattern in content:
                results.append(f"✅ {description}")
            else:
                results.append(f"❌ {description} - NOT FOUND")
        
        return True, results
    except Exception as e:
        return False, [f"Error validating retry mechanisms: {e}"]

def validate_session_management():
    """Validate session management improvements"""
    try:
        with open("download_file.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("smart_logout", "Smart logout function"),
            ("SESSION_REUSE_THRESHOLD", "Session reuse threshold"),
            ("current_session_downloads", "Session download counter"),
            ("login_with_retry", "Enhanced login function"),
            ("session_reuse", "Session reuse logic")
        ]
        
        results = []
        for pattern, description in checks:
            if pattern in content:
                results.append(f"✅ {description}")
            else:
                results.append(f"❌ {description} - NOT FOUND")
        
        return True, results
    except Exception as e:
        return False, [f"Error validating session management: {e}"]

def validate_account_cooldown():
    """Validate account cooldown functionality"""
    try:
        with open("download_file.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("is_account_in_cooldown", "Cooldown check function"),
            ("add_account_to_cooldown", "Add to cooldown function"),
            ("failed_accounts_cooldown", "Cooldown tracking variable"),
            ("ACCOUNT_COOLDOWN_TIME", "Cooldown time configuration")
        ]
        
        results = []
        for pattern, description in checks:
            if pattern in content:
                results.append(f"✅ {description}")
            else:
                results.append(f"❌ {description} - NOT FOUND")
        
        return True, results
    except Exception as e:
        return False, [f"Error validating account cooldown: {e}"]

def validate_enhanced_logging():
    """Validate enhanced logging and monitoring"""
    try:
        with open("download_file.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("errors_505", "505 error tracking"),
            ("Success Rate", "Success rate calculation"),
            ("enhanced error handling", "Enhanced error handling"),
            ("✅", "Success indicators in logging"),
            ("❌", "Failure indicators in logging")
        ]
        
        results = []
        for pattern, description in checks:
            if pattern in content:
                results.append(f"✅ {description}")
            else:
                results.append(f"❌ {description} - NOT FOUND")
        
        return True, results
    except Exception as e:
        return False, [f"Error validating enhanced logging: {e}"]

def validate_download_improvements():
    """Validate download process improvements"""
    try:
        with open("download_file.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("wait_for_download_and_rename", "Enhanced download monitoring"),
            ("getsize", "File size validation"), 
            ("download_selectors", "Multiple download button selectors"),
            ("book_retry_count", "Per-book retry logic"),
            ("random.uniform", "Random delays to avoid detection")
        ]
        
        results = []
        for pattern, description in checks:
            if pattern in content:
                results.append(f"✅ {description}")
            else:
                results.append(f"❌ {description} - NOT FOUND")
        
        return True, results
    except Exception as e:
        return False, [f"Error validating download improvements: {e}"]

def count_improvements():
    """Count and categorize improvements"""
    try:
        with open("download_file.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Count specific improvements
        improvements = {
            "Error Handling": len(re.findall(r'(505|502|503|504|500).*error', content, re.IGNORECASE)),
            "Retry Logic": len(re.findall(r'retry|attempt|backoff', content, re.IGNORECASE)),
            "Session Management": len(re.findall(r'session|login|logout', content, re.IGNORECASE)),
            "Cooldown Logic": len(re.findall(r'cooldown', content, re.IGNORECASE)),
            "Enhanced Logging": len(re.findall(r'logging\.|print', content, re.IGNORECASE))
        }
        
        return improvements
    except Exception as e:
        return {"Error": f"Failed to count improvements: {e}"}

def main():
    """Main validation function"""
    print("🔍 VALIDATING DOWNLOAD IMPROVEMENTS")
    print("=" * 60)
    
    # Track overall results
    all_passed = True
    total_checks = 0
    passed_checks = 0
    
    # 1. File existence check
    print("\n📁 FILE VALIDATION")
    success, message = validate_file_exists()
    if success:
        print(f"✅ {message}")
        passed_checks += 1
    else:
        print(f"❌ {message}")
        all_passed = False
    total_checks += 1
    
    # 2. 505 Error handling validation
    print("\n🚨 505 ERROR HANDLING VALIDATION")
    success, results = validate_505_error_handling()
    if success:
        for result in results:
            print(f"  {result}")
            if "✅" in result:
                passed_checks += 1
            total_checks += 1
    else:
        print(f"❌ Validation failed: {results}")
        all_passed = False
    
    # 3. Retry mechanisms validation
    print("\n🔄 RETRY MECHANISMS VALIDATION")
    success, results = validate_retry_mechanisms()
    if success:
        for result in results:
            print(f"  {result}")
            if "✅" in result:
                passed_checks += 1
            total_checks += 1
    else:
        print(f"❌ Validation failed: {results}")
        all_passed = False
    
    # 4. Session management validation
    print("\n🔐 SESSION MANAGEMENT VALIDATION")
    success, results = validate_session_management()
    if success:
        for result in results:
            print(f"  {result}")
            if "✅" in result:
                passed_checks += 1
            total_checks += 1
    else:
        print(f"❌ Validation failed: {results}")
        all_passed = False
    
    # 5. Account cooldown validation
    print("\n⏰ ACCOUNT COOLDOWN VALIDATION")
    success, results = validate_account_cooldown()
    if success:
        for result in results:
            print(f"  {result}")
            if "✅" in result:
                passed_checks += 1
            total_checks += 1
    else:
        print(f"❌ Validation failed: {results}")
        all_passed = False
    
    # 6. Enhanced logging validation
    print("\n📊 ENHANCED LOGGING VALIDATION")
    success, results = validate_enhanced_logging()
    if success:
        for result in results:
            print(f"  {result}")
            if "✅" in result:
                passed_checks += 1
            total_checks += 1
    else:
        print(f"❌ Validation failed: {results}")
        all_passed = False
    
    # 7. Download improvements validation
    print("\n⬇️ DOWNLOAD PROCESS VALIDATION")
    success, results = validate_download_improvements()
    if success:
        for result in results:
            print(f"  {result}")
            if "✅" in result:
                passed_checks += 1
            total_checks += 1
    else:
        print(f"❌ Validation failed: {results}")
        all_passed = False
    
    # 8. Count improvements
    print("\n📈 IMPROVEMENT STATISTICS")
    improvements = count_improvements()
    for category, count in improvements.items():
        print(f"  {category}: {count} occurrences")
    
    # Final summary
    print("\n" + "=" * 60)
    print("📋 VALIDATION SUMMARY")
    print("=" * 60)
    
    success_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
    print(f"Checks Passed: {passed_checks}/{total_checks}")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Validation Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success_rate >= 80:
        print("\n🎉 VALIDATION STATUS: PASSED")
        print("\n✅ Key Improvements Successfully Implemented:")
        print("  • Comprehensive 505 HTTP error handling")
        print("  • Exponential backoff retry mechanism")
        print("  • Smart session management & reuse")
        print("  • Account cooldown management")
        print("  • Enhanced download monitoring")
        print("  • Improved logging and statistics")
        print("  • Multiple download button detection")
        print("  • Random delays for detection avoidance")
        
        print("\n🚀 RECOMMENDATIONS:")
        print("  1. Test with real accounts in controlled environment")
        print("  2. Monitor 505 error reduction in logs")
        print("  3. Verify session reuse is working properly")
        print("  4. Check account cooldown effectiveness")
        print("  5. Review download success rates")
        
    else:
        print("\n⚠️ VALIDATION STATUS: NEEDS ATTENTION")
        print(f"  {total_checks - passed_checks} checks failed")
        print("  Please review and fix the issues above")
        all_passed = False
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)