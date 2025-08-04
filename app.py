import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pandas as pd
import logging

# Import the existing WhatsApp sender
from whatsapp_sender.sender import WhatsAppBulkSender
from whatsapp_sender.config import CONFIG

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "whatsapp-bulk-sender-secret-key")
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {
    'recipients': {'xlsx', 'xls'},
    'attachments': {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'txt'}
}

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global variables for progress tracking
current_progress = {
    'is_active': False,
    'current': 0,
    'total': 0,
    'logs': [],
    'success_count': 0,
    'failure_count': 0,
    'start_time': None,
    'end_time': None
}

# Mock data for demonstration
mock_customers = [
    {'id': 1, 'name': 'Sample', 'phone': '9840851742', 'email': '', 'status': 'Opted In'},
    {'id': 2, 'name': 'Test Customer UI', 'phone': '+15551234556', 'email': 'testui@example.com', 'status': 'Opted In'},
    {'id': 3, 'name': 'Integration Test Customer', 'phone': '+15559876554', 'email': 'integration@test.com', 'status': 'Opted In'},
    {'id': 4, 'name': 'Sample', 'phone': '+919840851742', 'email': '', 'status': 'Opted In'}
]

mock_campaigns = [
    {'id': 1, 'name': 'testing', 'description': 't', 'status': 'failed', 'created_at': '2024-01-15'},
    {'id': 2, 'name': 'Test 2', 'description': 'Sample Test', 'status': 'failed', 'created_at': '2024-01-16'},
    {'id': 3, 'name': 'Integration Test Campaign', 'description': 'Testing integration', 'status': 'completed', 'created_at': '2024-01-17'}
]

def allowed_file(filename, file_type):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS[file_type]

class ProgressTracker:
    """Custom progress tracker that integrates with WhatsAppBulkSender"""
    def __init__(self):
        self.logs = []
        self.current = 0
        self.total = 0
        self.success_count = 0
        self.failure_count = 0

    def log_message(self, message, msg_type='info'):
        """Add a log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        
        # Update global progress for API access
        current_progress['logs'] = self.logs
        current_progress['current'] = self.current
        current_progress['total'] = self.total
        current_progress['success_count'] = self.success_count
        current_progress['failure_count'] = self.failure_count
        
        print(log_entry)

    def update_progress(self, current, total):
        """Update progress counters"""
        self.current = current
        self.total = total
        current_progress['current'] = current
        current_progress['total'] = total

    def increment_success(self):
        """Increment success counter"""
        self.success_count += 1
        current_progress['success_count'] = self.success_count

    def increment_failure(self):
        """Increment failure counter"""
        self.failure_count += 1
        current_progress['failure_count'] = self.failure_count

class WhatsAppBulkSenderAPI(WhatsAppBulkSender):
    """Extended WhatsApp sender with API progress tracking"""
    
    def __init__(self, progress_tracker):
        super().__init__()
        self.tracker = progress_tracker

    def process_recipients_with_progress(self, recipients, attachment_path=None):
        """Process recipients with real-time progress updates"""
        self.stats['start_time'] = datetime.now()
        current_progress['start_time'] = self.stats['start_time'].isoformat()
        self.tracker.log_message("Starting WhatsApp bulk sending process...")
        self.tracker.update_progress(0, len(recipients))

        # Initialize WebDriver
        try:
            self.initialize_driver()
            self.tracker.log_message("Chrome WebDriver initialized successfully")
        except Exception as e:
            self.tracker.log_message(f"Failed to initialize WebDriver: {str(e)}", 'error')
            return False

        # Login to WhatsApp
        try:
            if not self.login_to_whatsapp():
                self.tracker.log_message("Failed to login to WhatsApp", 'error')
                return False
            self.tracker.log_message("Successfully logged into WhatsApp Web")
        except Exception as e:
            self.tracker.log_message(f"WhatsApp login error: {str(e)}", 'error')
            return False

        # Process each recipient
        for i, row in recipients.iterrows():
            contact = str(row['Contact']).strip()
            message = str(row.get('Message', '')).strip()

            self.tracker.log_message(f"Processing recipient {i+1}/{len(recipients)}: {contact}")
            self.tracker.update_progress(i, len(recipients))

            success = False
            for attempt in range(self.config['max_retries']):
                try:
                    if self.send_message(contact, message, attachment_path):
                        success = True
                        self.tracker.log_message(f"✓ Message sent successfully to {contact}")
                        self.tracker.increment_success()
                        break
                    else:
                        if attempt < self.config['max_retries'] - 1:
                            self.tracker.log_message(f"Retry {attempt + 1} for {contact}")
                        time.sleep(2)
                except Exception as e:
                    self.tracker.log_message(f"Error sending to {contact}: {str(e)}", 'error')
                    if attempt < self.config['max_retries'] - 1:
                        time.sleep(2)

            if not success:
                self.tracker.log_message(f"✗ Failed to send message to {contact}", 'error')
                self.tracker.increment_failure()

            # Update progress
            self.tracker.update_progress(i + 1, len(recipients))
            time.sleep(self.config['delay_between_messages'])

        # Cleanup
        try:
            if self.driver:
                self.driver.quit()
            self.tracker.log_message("WebDriver closed successfully")
        except Exception as e:
            self.tracker.log_message(f"Error closing WebDriver: {str(e)}", 'error')

        # Final summary
        self.stats['end_time'] = datetime.now()
        current_progress['end_time'] = self.stats['end_time'].isoformat()
        duration = self.stats['end_time'] - self.stats['start_time']
        self.tracker.log_message(
            f"Process completed! Success: {self.tracker.success_count}, "
            f"Failed: {self.tracker.failure_count}, Duration: {duration}"
        )

        return True

def send_messages_async(recipients_file, attachment_file=None):
    """Asynchronous message sending function"""
    global current_progress
    
    tracker = ProgressTracker()  # Initialize tracker at the beginning
    try:
        current_progress['is_active'] = True
        sender = WhatsAppBulkSenderAPI(tracker)

        # Load recipients
        tracker.log_message(f"Loading recipients from {recipients_file}")
        recipients = sender.load_recipient_data(recipients_file)
        tracker.log_message(f"Loaded {len(recipients)} recipients successfully")

        # Process recipients
        sender.process_recipients_with_progress(recipients, attachment_file)

    except Exception as e:
        tracker.log_message(f"Critical error: {str(e)}", 'error')
    finally:
        current_progress['is_active'] = False

# Dashboard Routes
@app.route('/')
def dashboard():
    """Main dashboard with statistics"""
    stats = {
        'total_customers': len(mock_customers),
        'total_campaigns': len(mock_campaigns),
        'active_campaigns': len([c for c in mock_campaigns if c['status'] == 'active']),
        'completed_campaigns': len([c for c in mock_campaigns if c['status'] == 'completed'])
    }
    return render_template('dashboard.html', stats=stats, recent_campaigns=mock_campaigns[:5])

@app.route('/customers')
def customers():
    """Customer management dashboard"""
    return render_template('customers.html', customers=mock_customers)

@app.route('/campaigns')
def campaigns():
    """Campaign management dashboard"""
    return render_template('campaigns.html', campaigns=mock_campaigns, customers=mock_customers)

@app.route('/whatsapp')
def whatsapp_connection():
    """WhatsApp connection status dashboard"""
    return render_template('whatsapp.html')

@app.route('/progress')
def progress():
    """Progress tracking dashboard"""
    return render_template('progress.html', progress=current_progress)

@app.route('/analytics')
def analytics():
    """Analytics dashboard"""
    return render_template('analytics.html')

@app.route('/settings')
def settings():
    """Settings dashboard"""
    return render_template('settings.html', config=CONFIG)

# API Routes
@app.route('/api/send', methods=['POST'])
def send_messages():
    """Main API endpoint to start sending messages"""
    global current_progress

    # Check if already processing
    if current_progress['is_active']:
        return jsonify({'error': 'Another sending process is already active'}), 400

    # Reset progress
    current_progress = {
        'is_active': False,
        'current': 0,
        'total': 0,
        'logs': [],
        'success_count': 0,
        'failure_count': 0,
        'start_time': None,
        'end_time': None
    }

    try:
        # Check if files are present
        if 'recipientsFile' not in request.files:
            return jsonify({'error': 'Recipients file is required'}), 400

        recipients_file = request.files['recipientsFile']
        attachment_file = request.files.get('attachmentFile')

        # Validate recipients file
        if recipients_file.filename == '':
            return jsonify({'error': 'No recipients file selected'}), 400

        if not allowed_file(recipients_file.filename, 'recipients'):
            return jsonify({'error': 'Invalid recipients file format. Use .xlsx or .xls'}), 400

        # Save recipients file
        recipients_filename = secure_filename(recipients_file.filename or "recipients.xlsx")
        recipients_path = os.path.join(UPLOAD_FOLDER, f"recipients_{int(time.time())}_{recipients_filename}")
        recipients_file.save(recipients_path)

        # Save attachment file if provided
        attachment_path = None
        if attachment_file and attachment_file.filename != '':
            if not allowed_file(attachment_file.filename, 'attachments'):
                return jsonify({'error': 'Invalid attachment file format'}), 400

            attachment_filename = secure_filename(attachment_file.filename or "attachment.pdf")
            attachment_path = os.path.join(UPLOAD_FOLDER, f"attachment_{int(time.time())}_{attachment_filename}")
            attachment_file.save(attachment_path)

        # Start async processing
        thread = threading.Thread(
            target=send_messages_async,
            args=(recipients_path, attachment_path)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'message': 'Message sending started',
            'status': 'processing'
        })

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get current sending progress"""
    return jsonify(current_progress)

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get final status after completion"""
    if current_progress['is_active']:
        return jsonify({'status': 'processing', 'progress': current_progress})
    else:
        return jsonify({
            'status': 'completed',
            'successCount': current_progress['success_count'],
            'failureCount': current_progress['failure_count'],
            'logs': current_progress['logs']
        })

@app.route('/api/customers', methods=['GET'])
def get_customers():
    """Get all customers"""
    return jsonify(mock_customers)

@app.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    """Get all campaigns"""
    return jsonify(mock_campaigns)

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get analytics data"""
    analytics_data = {
        'success_rate': 85,
        'failure_rate': 15,
        'monthly_campaigns': [12, 15, 18, 22, 19, 25],
        'customer_growth': [100, 150, 200, 280, 350, 420],
        'message_volume': [1200, 1800, 2200, 2800, 3200, 3800]
    }
    return jsonify(analytics_data)

if __name__ == '__main__':
    print("Starting WhatsApp Bulk Sender Multi-Dashboard Application...")
    print("Access the application at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
