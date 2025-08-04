import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
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

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///whatsapp_bulk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

# Database Models
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), default='Opted In')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email or '',
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'message': self.message or '',
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d'),
            'sent_count': self.sent_count,
            'failed_count': self.failed_count
        }

# Initialize database
with app.app_context():
    db.create_all()
    
    # Add sample data if database is empty
    if Customer.query.count() == 0:
        sample_customers = [
            Customer(name='Sample', phone='9840851742', email='', status='Opted In'),
            Customer(name='Test Customer UI', phone='+15551234556', email='testui@example.com', status='Opted In'),
            Customer(name='Integration Test Customer', phone='+15559876554', email='integration@test.com', status='Opted In'),
            Customer(name='Sample User', phone='+919840851742', email='', status='Opted In')
        ]
        for customer in sample_customers:
            db.session.add(customer)
        
        sample_campaigns = [
            Campaign(name='testing', description='t', status='failed'),
            Campaign(name='Test 2', description='Sample Test', status='failed'),
            Campaign(name='Integration Test Campaign', description='Testing integration', status='completed')
        ]
        for campaign in sample_campaigns:
            db.session.add(campaign)
        
        db.session.commit()

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
    customers_count = Customer.query.count()
    campaigns_list = Campaign.query.all()
    stats = {
        'total_customers': customers_count,
        'total_campaigns': len(campaigns_list),
        'active_campaigns': len([c for c in campaigns_list if c.status == 'active']),
        'completed_campaigns': len([c for c in campaigns_list if c.status == 'completed'])
    }
    recent_campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()
    return render_template('dashboard.html', stats=stats, recent_campaigns=recent_campaigns)

@app.route('/customers')
def customers():
    """Customer management dashboard"""
    customers_list = Customer.query.all()
    return render_template('customers.html', customers=customers_list)

@app.route('/campaigns')
def campaigns():
    """Campaign management dashboard"""
    campaigns_list = Campaign.query.all()
    customers_list = Customer.query.all()
    return render_template('campaigns.html', campaigns=campaigns_list, customers=customers_list)

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
    customers_list = Customer.query.all()
    return jsonify([customer.to_dict() for customer in customers_list])

@app.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    """Get all campaigns"""
    campaigns_list = Campaign.query.all()
    return jsonify([campaign.to_dict() for campaign in campaigns_list])

# Removed duplicate analytics function - using real database version below

# Customer Management API Endpoints
@app.route('/api/customers', methods=['POST'])
def add_customer():
    """Add a new customer"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('phone'):
            return jsonify({'error': 'Name and phone are required'}), 400
        
        # Check if phone already exists
        existing_customer = Customer.query.filter_by(phone=data['phone']).first()
        if existing_customer:
            return jsonify({'error': 'Customer with this phone number already exists'}), 400
        
        # Create new customer
        customer = Customer(
            name=data['name'],
            phone=data['phone'],
            email=data.get('email', ''),
            status=data.get('status', 'Opted In')
        )
        
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({'message': 'Customer added successfully', 'customer': customer.to_dict()}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to add customer: {str(e)}'}), 500

@app.route('/api/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """Get a specific customer"""
    customer = Customer.query.get_or_404(customer_id)
    return jsonify(customer.to_dict())

@app.route('/api/customers/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    """Update a customer"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            customer.name = data['name']
        if 'phone' in data:
            # Check if new phone already exists for another customer
            existing = Customer.query.filter(Customer.phone == data['phone'], Customer.id != customer_id).first()
            if existing:
                return jsonify({'error': 'Phone number already exists'}), 400
            customer.phone = data['phone']
        if 'email' in data:
            customer.email = data['email']
        if 'status' in data:
            customer.status = data['status']
        
        db.session.commit()
        return jsonify({'message': 'Customer updated successfully', 'customer': customer.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update customer: {str(e)}'}), 500

@app.route('/api/customers/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    """Delete a customer"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        db.session.delete(customer)
        db.session.commit()
        return jsonify({'message': 'Customer deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete customer: {str(e)}'}), 500

@app.route('/api/customers/upload', methods=['POST'])
def upload_customers():
    """Upload customers from Excel file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename, 'recipients'):
            return jsonify({'error': 'Invalid file format. Please upload Excel files only.'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Read Excel file
        df = pd.read_excel(filepath)
        
        # Validate columns
        required_columns = ['Name', 'Phone']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400
        
        added_customers = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                name = str(row['Name']).strip()
                phone = str(row['Phone']).strip()
                email = str(row.get('Email', '')).strip() if pd.notna(row.get('Email')) else ''
                
                if not name or not phone:
                    errors.append(f'Row {index + 2}: Name and Phone are required')
                    continue
                
                # Check if customer already exists
                existing = Customer.query.filter_by(phone=phone).first()
                if existing:
                    errors.append(f'Row {index + 2}: Customer with phone {phone} already exists')
                    continue
                
                customer = Customer(name=name, phone=phone, email=email)
                db.session.add(customer)
                added_customers.append(customer.to_dict())
                
            except Exception as e:
                errors.append(f'Row {index + 2}: {str(e)}')
        
        db.session.commit()
        
        # Clean up uploaded file
        os.remove(filepath)
        
        return jsonify({
            'message': f'Successfully added {len(added_customers)} customers',
            'added_customers': added_customers,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to process file: {str(e)}'}), 500

# Campaign Management API Endpoints
@app.route('/api/campaigns', methods=['POST'])
def create_campaign():
    """Create a new campaign"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('message'):
            return jsonify({'error': 'Campaign name and message are required'}), 400
        
        # Create new campaign
        campaign = Campaign(
            name=data['name'],
            description=data.get('description', ''),
            message=data['message'],
            status='draft'
        )
        
        db.session.add(campaign)
        db.session.commit()
        
        return jsonify({'message': 'Campaign created successfully', 'campaign': campaign.to_dict()}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create campaign: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>', methods=['GET'])
def get_campaign(campaign_id):
    """Get a specific campaign"""
    campaign = Campaign.query.get_or_404(campaign_id)
    return jsonify(campaign.to_dict())

@app.route('/api/campaigns/<int:campaign_id>', methods=['DELETE'])
def delete_campaign(campaign_id):
    """Delete a campaign"""
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        db.session.delete(campaign)
        db.session.commit()
        return jsonify({'message': 'Campaign deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete campaign: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/duplicate', methods=['POST'])
def duplicate_campaign(campaign_id):
    """Duplicate a campaign"""
    try:
        original = Campaign.query.get_or_404(campaign_id)
        
        duplicate = Campaign(
            name=f"{original.name} (Copy)",
            description=original.description,
            message=original.message,
            status='draft'
        )
        
        db.session.add(duplicate)
        db.session.commit()
        
        return jsonify({'message': 'Campaign duplicated successfully', 'campaign': duplicate.to_dict()}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to duplicate campaign: {str(e)}'}), 500

# QR Code API
@app.route('/api/whatsapp/qr', methods=['GET'])
def get_qr_code():
    """Get QR code from WhatsApp Web using proper WebDriver initialization"""
    try:
        from whatsapp_sender.sender import WhatsAppBulkSender
        
        sender = WhatsAppBulkSender()
        
        # Initialize WebDriver
        try:
            sender.initialize_driver()
            print("Chrome WebDriver initialized successfully for QR capture")
        except Exception as e:
            print(f"Failed to initialize WebDriver: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'WebDriver initialization failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        
        # Capture QR code using the new method
        try:
            qr_result = sender.capture_qr_code()
            
            if qr_result == "already_connected":
                print("WhatsApp Web already connected")
                return jsonify({
                    'success': True,
                    'already_connected': True,
                    'message': 'WhatsApp Web is already connected - no QR code needed',
                    'timestamp': datetime.now().isoformat()
                })
            elif qr_result:
                print("QR code captured successfully")
                return jsonify({
                    'success': True,
                    'qr_code': qr_result,
                    'message': 'QR code captured successfully',
                    'timestamp': datetime.now().isoformat()
                })
            else:
                print("QR code capture failed")
                return jsonify({
                    'success': False,
                    'message': 'Could not capture QR code - please try again',
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f"QR code capture error: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'QR capture failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        finally:
            if hasattr(sender, 'driver') and sender.driver:
                sender.driver.quit()
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to initialize QR code capture: {str(e)}',
            'timestamp': datetime.now().isoformat()
        })

# WhatsApp Connection API
@app.route('/api/whatsapp/status', methods=['GET'])
def get_whatsapp_status():
    """Check WhatsApp connection status using proper WebDriver initialization"""
    try:
        from whatsapp_sender.sender import WhatsAppBulkSender
        
        sender = WhatsAppBulkSender()
        
        # Initialize WebDriver
        try:
            sender.initialize_driver()
            print("Chrome WebDriver initialized successfully")
        except Exception as e:
            print(f"Failed to initialize WebDriver: {str(e)}")
            return jsonify({
                'connected': False,
                'status': 'error',
                'message': f'WebDriver initialization failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        
        # Check WhatsApp login status
        try:
            if sender.login_to_whatsapp():
                print("Successfully logged into WhatsApp Web")
                status = {
                    'connected': True,
                    'status': 'connected',
                    'message': 'WhatsApp Web is connected and ready',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                print("QR code scan required")
                status = {
                    'connected': False,
                    'status': 'qr_required',
                    'message': 'QR code scan required to connect',
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            print(f"WhatsApp login check error: {str(e)}")
            status = {
                'connected': False,
                'status': 'error',
                'message': f'Login check failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
        finally:
            if hasattr(sender, 'driver') and sender.driver:
                sender.driver.quit()
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({
            'connected': False,
            'status': 'error',
            'message': f'Connection check failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        })

# Analytics API - Real Database Data
@app.route('/api/analytics', methods=['GET'])
def get_real_analytics():
    try:
        # Get counts from database
        total_customers = Customer.query.count()
        opted_in_customers = Customer.query.filter_by(status='Opted In').count()
        total_campaigns = Campaign.query.count()
        
        # Calculate campaign status distribution
        draft_campaigns = Campaign.query.filter_by(status='draft').count()
        completed_campaigns = Campaign.query.filter_by(status='completed').count()
        active_campaigns = Campaign.query.filter_by(status='active').count()
        
        # Get customer status distribution
        opted_out_customers = Customer.query.filter_by(status='Opted Out').count()
        pending_customers = Customer.query.filter_by(status='Pending').count()
        
        # Get recent campaigns
        recent_campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()
        
        analytics_data = {
            'total_customers': total_customers,
            'opted_in_customers': opted_in_customers,
            'opted_out_customers': opted_out_customers,
            'pending_customers': pending_customers,
            'total_campaigns': total_campaigns,
            'draft_campaigns': draft_campaigns,
            'completed_campaigns': completed_campaigns,
            'active_campaigns': active_campaigns,
            'recent_campaigns': [
                {
                    'id': campaign.id,
                    'name': campaign.name,
                    'status': campaign.status,
                    'message': campaign.message[:50] + '...' if len(campaign.message) > 50 else campaign.message,
                    'created_at': campaign.created_at.strftime('%Y-%m-%d %H:%M')
                }
                for campaign in recent_campaigns
            ]
        }
        
        return jsonify(analytics_data)
        
    except Exception as e:
        return jsonify({'error': f'Failed to get analytics: {str(e)}'}), 500

# Settings API
@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings"""
    return jsonify(CONFIG)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update settings"""
    try:
        data = request.get_json()
        
        # Update CONFIG values
        for key, value in data.items():
            if key in CONFIG:
                CONFIG[key] = value
        
        return jsonify({'message': 'Settings updated successfully', 'config': CONFIG})
        
    except Exception as e:
        return jsonify({'error': f'Failed to update settings: {str(e)}'}), 500

# Backup and Restore API
@app.route('/api/backup', methods=['GET'])
def create_backup():
    """Create database backup"""
    try:
        import json
        from datetime import datetime
        
        # Get all data
        customers = Customer.query.all()
        campaigns = Campaign.query.all()
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'customers': [customer.to_dict() for customer in customers],
            'campaigns': [campaign.to_dict() for campaign in campaigns],
            'settings': CONFIG
        }
        
        # Save backup file
        backup_filename = f"whatsapp_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = os.path.join(UPLOAD_FOLDER, backup_filename)
        
        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        return jsonify({
            'message': 'Backup created successfully',
            'filename': backup_filename,
            'path': backup_path,
            'customers_count': len(customers),
            'campaigns_count': len(campaigns)
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to create backup: {str(e)}'}), 500

@app.route('/api/restore', methods=['POST'])
def restore_backup():
    """Restore from backup file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No backup file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Read backup data
        with open(filepath, 'r') as f:
            backup_data = json.load(f)
        
        # Clear existing data
        Campaign.query.delete()
        Customer.query.delete()
        
        # Restore customers
        for customer_data in backup_data.get('customers', []):
            customer = Customer(
                name=customer_data['name'],
                phone=customer_data['phone'],
                email=customer_data.get('email', ''),
                status=customer_data.get('status', 'Opted In')
            )
            db.session.add(customer)
        
        # Restore campaigns
        for campaign_data in backup_data.get('campaigns', []):
            campaign = Campaign(
                name=campaign_data['name'],
                description=campaign_data.get('description', ''),
                message=campaign_data.get('message', ''),
                status=campaign_data.get('status', 'draft')
            )
            db.session.add(campaign)
        
        db.session.commit()
        
        # Clean up uploaded file
        os.remove(filepath)
        
        return jsonify({
            'message': 'Backup restored successfully',
            'customers_restored': len(backup_data.get('customers', [])),
            'campaigns_restored': len(backup_data.get('campaigns', []))
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to restore backup: {str(e)}'}), 500

if __name__ == '__main__':
    print("Starting WhatsApp Bulk Sender Multi-Dashboard Application...")
    print("Access the application at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
