#!/usr/bin/env python3
"""
Comprehensive Test Suite for All Bot Functions
Tests database operations, user bot interactions, and admin panel functionality
"""

import os
import csv
import json
import sqlite3
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/test_bot_functions.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_sample_book_data():
    """Create sample book data for testing"""
    books_data = [
        {
            'id': 'book_001',
            'title': 'Python Programming for Beginners',
            'author': 'John Smith',
            'category': 'Programming',
            'year': '2023',
            'isbn': '978-1234567890',
            'pages': '350',
            'language': 'English',
            'description': 'Complete guide to Python programming',
            'publisher': 'Tech Books',
            'format': 'PDF',
            'size': '15.2MB',
            'available': 'yes'
        },
        {
            'id': 'book_002',
            'title': 'Data Science with Python',
            'author': 'Jane Doe',
            'category': 'Data Science',
            'year': '2023',
            'isbn': '978-0987654321',
            'pages': '420',
            'language': 'English',
            'description': 'Comprehensive data science guide',
            'publisher': 'Data Press',
            'format': 'PDF',
            'size': '18.5MB',
            'available': 'yes'
        },
        {
            'id': 'book_003',
            'title': 'Machine Learning Fundamentals',
            'author': 'Bob Johnson',
            'category': 'AI/ML',
            'year': '2022',
            'isbn': '978-1122334455',
            'pages': '500',
            'language': 'English',
            'description': 'Introduction to machine learning concepts',
            'publisher': 'AI Publications',
            'format': 'PDF',
            'size': '22.1MB',
            'available': 'no'
        },
        {
            'id': 'book_004',
            'title': 'Web Development Complete Guide',
            'author': 'Alice Brown',
            'category': 'Web Development',
            'year': '2023',
            'isbn': '978-2233445566',
            'pages': '380',
            'language': 'English',
            'description': 'Full-stack web development tutorial',
            'publisher': 'Web Masters',
            'format': 'PDF',
            'size': '16.8MB',
            'available': 'yes'
        },
        {
            'id': 'book_005',
            'title': 'Database Design Principles',
            'author': 'Charlie Wilson',
            'category': 'Database',
            'year': '2022',
            'isbn': '978-3344556677',
            'pages': '290',
            'language': 'English',
            'description': 'Database design and optimization guide',
            'publisher': 'DB Books',
            'format': 'PDF',
            'size': '12.3MB',
            'available': 'yes'
        }
    ]
    
    # Create CSV file
    csv_path = 'data/books_database.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = books_data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(books_data)
    
    logger.info(f"Created sample book data with {len(books_data)} books at {csv_path}")
    return csv_path

def test_admin_database():
    """Test admin database functionality"""
    logger.info("=== Testing Admin Database ===")
    
    try:
        # Import admin database
        from admin_database import AdminDatabase, get_admin_db
        
        # Initialize database
        admin_db = AdminDatabase()
        
        # Test 1: Search books
        logger.info("Test 1: Searching books")
        search_results = admin_db.search_books("python")
        logger.info(f"Search results for 'python': {len(search_results)} books found")
        for book in search_results[:2]:  # Show first 2 results
            logger.info(f"  - {book['title']} by {book['author']}")
        
        # Test 2: Create user session
        logger.info("Test 2: Creating user session")
        session_id = admin_db.create_user_session("test_user_123")
        logger.info(f"Created session: {session_id}")
        
        # Test 3: Add books to request
        logger.info("Test 3: Adding books to request")
        if search_results:
            book_id = search_results[0]['id']
            success = admin_db.add_book_to_request(session_id, book_id)
            logger.info(f"Added book {book_id} to request: {success}")
        
        # Test 4: Get request summary
        logger.info("Test 4: Getting request summary")
        summary = admin_db.get_request_summary(session_id)
        logger.info(f"Request summary: {len(summary)} books in list")
        
        # Test 5: Submit request
        logger.info("Test 5: Submitting request")
        request_id = admin_db.submit_request(session_id)
        logger.info(f"Submitted request: {request_id}")
        
        # Test 6: Get pending requests
        logger.info("Test 6: Getting pending requests")
        pending = admin_db.get_pending_requests()
        logger.info(f"Pending requests: {len(pending)}")
        
        # Test 7: Approve request
        if pending:
            logger.info("Test 7: Approving request")
            success = admin_db.approve_request(pending[0]['id'], "Download links will be sent")
            logger.info(f"Approved request: {success}")
        
        logger.info("✅ Admin Database tests completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Admin Database test failed: {e}")
        return False

def test_user_bot_functions():
    """Test user bot functionality"""
    logger.info("=== Testing User Bot Functions ===")
    
    try:
        # Import user bot
        from user_book_bot import UserBookBot
        
        # Initialize bot (without actual Telegram connection)
        user_bot = UserBookBot()
        
        # Test 1: Search functionality
        logger.info("Test 1: Testing search functionality")
        search_query = "python programming"
        results = user_bot.admin_db.search_books(search_query)
        logger.info(f"Search for '{search_query}': {len(results)} results")
        
        # Test 2: Session management
        logger.info("Test 2: Testing session management")
        test_user_id = "test_user_456"
        session_id = user_bot.get_or_create_session(test_user_id)
        logger.info(f"Session for user {test_user_id}: {session_id}")
        
        # Test 3: Add book to list
        logger.info("Test 3: Testing add book to list")
        if results:
            book_id = results[0]['id']
            success = user_bot.admin_db.add_book_to_request(session_id, book_id)
            logger.info(f"Added book to list: {success}")
        
        # Test 4: View list
        logger.info("Test 4: Testing view list")
        user_list = user_bot.admin_db.get_request_summary(session_id)
        logger.info(f"User list contains: {len(user_list)} books")
        
        # Test 5: Clear list
        logger.info("Test 5: Testing clear list")
        cleared = user_bot.admin_db.clear_request(session_id)
        logger.info(f"List cleared: {cleared}")
        
        # Test 6: Stats
        logger.info("Test 6: Testing stats")
        stats = user_bot.admin_db.get_user_stats(test_user_id)
        logger.info(f"User stats: {stats}")
        
        logger.info("✅ User Bot tests completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ User Bot test failed: {e}")
        return False

def test_admin_panel_functions():
    """Test admin panel functionality"""
    logger.info("=== Testing Admin Panel Functions ===")
    
    try:
        # Import admin panel
        from admin_panel import AdminPanel
        
        # Initialize admin panel
        admin_panel = AdminPanel()
        
        # Test 1: Dashboard stats
        logger.info("Test 1: Testing dashboard stats")
        stats = admin_panel.get_dashboard_stats()
        logger.info(f"Dashboard stats: {stats}")
        
        # Test 2: Pending requests
        logger.info("Test 2: Testing pending requests")
        pending = admin_panel.admin_db.get_pending_requests()
        logger.info(f"Pending requests: {len(pending)}")
        
        # Test 3: Auto-process requests
        logger.info("Test 3: Testing auto-process")
        processed = admin_panel.auto_process_requests()
        logger.info(f"Auto-processed requests: {processed}")
        
        # Test 4: Request details
        if pending:
            logger.info("Test 4: Testing request details")
            request_id = pending[0]['id']
            details = admin_panel.admin_db.get_request_details(request_id)
            logger.info(f"Request details for {request_id}: {len(details)} items")
        
        logger.info("✅ Admin Panel tests completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Admin Panel test failed: {e}")
        return False

def test_whatsapp_notifications():
    """Test WhatsApp notification system"""
    logger.info("=== Testing WhatsApp Notifications ===")
    
    try:
        from admin_database import get_admin_db
        
        admin_db = get_admin_db()
        
        # Test notification sending (mock)
        logger.info("Test 1: Testing WhatsApp notification")
        message = "Test notification: New book request submitted"
        success = admin_db.send_whatsapp_notification(message)
        logger.info(f"WhatsApp notification sent: {success}")
        
        logger.info("✅ WhatsApp Notification tests completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ WhatsApp Notification test failed: {e}")
        return False

def test_csv_database_export():
    """Test CSV database export functionality"""
    logger.info("=== Testing CSV Database Export ===")
    
    try:
        from admin_database import get_admin_db
        
        admin_db = get_admin_db()
        
        # Test 1: Export all data to CSV
        logger.info("Test 1: Exporting database to CSV")
        
        # Export books
        books_export_path = "data/exported_books.csv"
        books = admin_db.get_all_books()
        
        with open(books_export_path, 'w', newline='', encoding='utf-8') as csvfile:
            if books:
                fieldnames = books[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(books)
        
        logger.info(f"Exported {len(books)} books to {books_export_path}")
        
        # Export requests
        requests_export_path = "data/exported_requests.csv"
        requests = admin_db.get_all_requests()
        
        with open(requests_export_path, 'w', newline='', encoding='utf-8') as csvfile:
            if requests:
                fieldnames = requests[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(requests)
        
        logger.info(f"Exported {len(requests)} requests to {requests_export_path}")
        
        logger.info("✅ CSV Database Export tests completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ CSV Database Export test failed: {e}")
        return False

def run_integration_test():
    """Run complete integration test"""
    logger.info("=== Running Integration Test ===")
    
    try:
        from admin_database import get_admin_db
        from user_book_bot import UserBookBot
        from admin_panel import AdminPanel
        
        # Simulate complete user flow
        logger.info("Integration Test: Complete user flow simulation")
        
        # Step 1: User searches for books
        user_bot = UserBookBot()
        test_user_id = "integration_test_user"
        session_id = user_bot.get_or_create_session(test_user_id)
        
        # Step 2: User adds books to list
        search_results = user_bot.admin_db.search_books("programming")
        if search_results:
            for book in search_results[:2]:  # Add first 2 books
                user_bot.admin_db.add_book_to_request(session_id, book['id'])
        
        # Step 3: User submits request
        request_id = user_bot.admin_db.submit_request(session_id)
        logger.info(f"Integration: User submitted request {request_id}")
        
        # Step 4: Admin processes request
        admin_panel = AdminPanel()
        pending = admin_panel.admin_db.get_pending_requests()
        
        if pending:
            # Auto-approve available books
            admin_panel.auto_process_requests()
            logger.info("Integration: Admin auto-processed requests")
        
        # Step 5: Export final data
        logger.info("Integration: Exporting final database state")
        
        # Generate final report
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_books': len(user_bot.admin_db.get_all_books()),
            'total_requests': len(user_bot.admin_db.get_all_requests()),
            'pending_requests': len(user_bot.admin_db.get_pending_requests()),
            'test_status': 'completed'
        }
        
        with open('data/integration_test_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("✅ Integration test completed successfully")
        logger.info(f"Final report: {report}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🚀 Starting comprehensive bot function tests")
    
    # Create sample data first
    create_sample_book_data()
    
    # Track test results
    test_results = {}
    
    # Run all tests
    test_results['admin_database'] = test_admin_database()
    test_results['user_bot'] = test_user_bot_functions()
    test_results['admin_panel'] = test_admin_panel_functions()
    test_results['whatsapp_notifications'] = test_whatsapp_notifications()
    test_results['csv_export'] = test_csv_database_export()
    test_results['integration'] = run_integration_test()
    
    # Summary
    logger.info("=== TEST SUMMARY ===")
    passed = sum(test_results.values())
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"Overall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Bot system is ready for deployment.")
    else:
        logger.info("⚠️  Some tests failed. Please check the logs for details.")
    
    return test_results

if __name__ == "__main__":
    main()