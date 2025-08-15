import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, current_app, render_template, request, jsonify, redirect, url_for, flash, session
from flask import request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pandas as pd
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import sqlite3
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Import the existing WhatsApp sender
from whatsapp_sender.sender import WhatsAppBulkSender
from whatsapp_sender.config import CONFIG

# Global WhatsApp sender instance
whatsapp_sender = None

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "whatsapp-bulk-sender-secret-key")
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+os.path.join(app.instance_path, 'whatsapp_bulk.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'timeout': 30}}
db = SQLAlchemy(app)

# ensure SQLite enforces foreign key constraints
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    # Only for SQLite connections
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# --- APScheduler Configuration ---
jobstores = {'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])}
scheduler = BackgroundScheduler(jobstores=jobstores)

# --- ADD THIS CODE BLOCK ---
def start_scheduler():
    """
    Starts the APScheduler, ensuring it only runs in the main process,
    avoiding conflicts with the Flask reloader.
    """
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        # In debug mode, this function will be called twice. We want to start
        # the scheduler only in the child process (the one that runs the app).
        return
    
    if not scheduler.running:
        scheduler.start()
        app.logger.info("APScheduler started successfully.")

# Call the function to start the scheduler
start_scheduler()

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
    created_at = db.Column(db.DateTime, default=datetime.now)
    
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
    created_at = db.Column(db.DateTime, default=datetime.now)
    scheduled_at = db.Column(db.DateTime, nullable=True)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    attachment_path=db.Column(db.String(100),nullable=True)

    # CHANGED: Use back_populates to explicitly link to the 'campaign' attribute on the other model
    recipients = db.relationship(
        'CampaignRecipient',
        back_populates='campaign',
        lazy='dynamic',
        cascade='all, delete-orphan',
        passive_deletes=True
    )

    def to_dict(self):
        # ... (your to_dict method remains the same) ...
        #print("\n\n\nDATE",self.scheduled_at)
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'message': self.message or '',
            'scheduled_Date':self.scheduled_at.strftime('%Y-%m-%dT%H:%M') if self.scheduled_at else None,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d'),
            'sent_count': self.sent_count,
            'failed_count': self.failed_count,
            'attachments':self.attachment_path
        }


class CampaignRecipient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id', ondelete='CASCADE'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    
    # ENSURE THIS LINE EXISTS EXACTLY AS WRITTEN:
    status = db.Column(db.String(20), default='pending')
    
    attempts = db.Column(db.Integer, default=0)
    recipient_name = db.Column(db.String(100), nullable=False)
    recipient_phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    customer = db.relationship('Customer', lazy='joined')
    campaign = db.relationship('Campaign', back_populates='recipients')

    def to_dict(self):
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'recipient_name': self.recipient_name,
            'recipient_phone': self.recipient_phone,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Initialize database
with app.app_context():
    db.create_all()

def allowed_file(filename, file_type):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS[file_type]

def normalize_phone_to_digits(phone):
    """Return phone digits only. Caller should ensure country code is present when needed."""
    if not phone:
        return ''
    s = ''.join(ch for ch in str(phone) if ch.isdigit())
    return s

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
    
    def __init__(self, progress_tracker=None):
        super().__init__()
        self.tracker = progress_tracker if progress_tracker else ProgressTracker()

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


def send_messages_async(recipients_path, attachment_path=None):
    """Asynchronous message sending function using the global sender instance."""
    global current_progress, whatsapp_sender

    try:
        if whatsapp_sender is None or not whatsapp_sender.is_driver_active():
            raise Exception("WhatsApp is not connected. Please connect first.")

        # Wait for login confirmation
        if not whatsapp_sender.wait_for_login():
            raise Exception("WhatsApp login failed or timed out.")

        # Each sending job gets a new tracker.
        whatsapp_sender.tracker = ProgressTracker()
        
        # Load recipients from file
        recipients_df = pd.read_excel(recipients_path)
        
        # Process recipients with progress updates
        whatsapp_sender.process_recipients_with_progress(recipients_df, attachment_path)
        
    except Exception as e:
        current_progress['logs'].append(f"[ERROR] {str(e)}")
    finally:
        # Finalize progress, but DO NOT quit the driver
        current_progress['is_active'] = False
        current_progress['end_time'] = datetime.now().isoformat()

def process_campaign_async(campaign_id, attachment_path=None):
    """
    Background thread worker to process a campaign by id.
    Uses the global whatsapp_sender instance (WhatsAppBulkSenderAPI).
    """
    global whatsapp_sender, current_progress

    with app.app_context():
        try:
            # Basic fetch & guard
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                current_app.logger.error(f"Campaign {campaign_id} not found")
                return

            # Prevent double-processing: only run queued campaigns
            if campaign.status not in ('queued', 'scheduled'):
                current_app.logger.info(f"Campaign {campaign_id} status is {campaign.status}; skipping worker start.")
                return

            # load recipients
            recipients = CampaignRecipient.query.filter_by(campaign_id=campaign_id).all()
            total = len(recipients)
            #print(total,recipients,"\n\n\n\this is the totalt list \n\n\n\n")

            # initialize progress
            current_progress.update({
                'is_active': True,
                'current': 0,
                'total': total,
                'logs': [],
                'success_count': 0,
                'failure_count': 0,
                'start_time': datetime.now().isoformat(),
                'end_time': None
            })
            print("all instance set up done")
            # ensure sender is initialized
            if whatsapp_sender is None or not whatsapp_sender.is_driver_active():
                whatsapp_sender = WhatsAppBulkSenderAPI()
                try:
                    whatsapp_sender.initialize_driver()
                    whatsapp_sender.login_to_whatsapp_with_wait()
                except Exception as e:
                    msg = f"WebDriver init failed: {str(e)}"
                    current_progress['logs'].append(f"[ERROR] {msg}")
                    current_progress['is_active'] = False
                    current_app.logger.exception(msg)
                    return

            # ensure logged in (wait)
            if not whatsapp_sender.wait_for_login():
                print("testing login")
                msg = "WhatsApp login failed or timeout."
                current_progress['logs'].append(f"[ERROR] {msg}")
                current_progress['is_active'] = False
                current_app.logger.error(msg)
                return
            print("login was sucess")
            # mark campaign running
            campaign.status = 'running'
            db.session.commit()

            # iterate recipients one-by-one (DB-driven)
            idx = 0
            for r in recipients:
                # check for cancel request
                #print("recipets:                ",r,"\n\n\n")
                db.session.refresh(campaign)
                if campaign.status == 'cancel_requested':
                    campaign.status = 'cancelled'
                    db.session.commit()
                    current_progress['logs'].append(f"Campaign {campaign_id} cancelled by user.")
                    break

                idx += 1
                customer = Customer.query.get(r.customer_id)
                if not customer:
                    r.status = 'failed'
                    r.last_error = 'Customer not found'
                    r.attempts = (r.attempts or 0) + 1
                    r.updated_at = datetime.now()
                    db.session.commit()
                    current_progress['failure_count'] += 1
                    current_progress['current'] = idx
                    current_progress['logs'].append(f"[{idx}/{total}] Customer {r.customer_id} not found")
                    continue

                raw_phone = customer.phone
                phone = normalize_phone_to_digits(raw_phone)
                message = campaign.message or ''

                current_progress['logs'].append(f"[{idx}/{total}] Sending to {phone}")
                current_progress['current'] = idx

                success = False
                last_err = None
                attempts = 0
                max_retries = int(getattr(whatsapp_sender, 'config', {}).get('max_retries', 2))

                # Quick phone validation (basic)
                if not phone or len(phone) < 8:
                    last_err = "Invalid phone number"
                    attempts = (r.attempts or 0) + 1
                    r.attempts = attempts
                    r.last_error = last_err
                    r.status = 'failed'
                    r.updated_at = datetime.now()
                    db.session.commit()
                    current_progress['failure_count'] += 1
                    current_progress['logs'].append(f"[{idx}/{total}] Invalid phone for customer {customer.id}")
                    # short sleep and continue
                    time.sleep(0.5)
                    continue
                print("max apptemps",max_retries)
                # perform attempts with backoff
                for attempt in range(1, max_retries + 1):
                    attempts = attempt
                    try:
                        ok = whatsapp_sender.send_message(phone, message, attachment_path)
                        if ok:
                            success = True
                            break
                        else:
                            last_err = 'send_message returned False'
                    except Exception as e:
                        last_err = str(e)
                        current_app.logger.exception(f"Error sending to {phone}: {e}")

                    # small backoff before next retry
                    time.sleep(int(getattr(whatsapp_sender, 'config', {}).get('delay_between_messages', 1.5)))

                # update recipient row
                r.attempts = (r.attempts or 0) + attempts
                r.last_error = last_err
                r.updated_at = datetime.now()

                if success:
                    r.status = 'sent'
                    r.sent_at = datetime.now()
                    current_progress['success_count'] += 1
                    current_progress['logs'].append(f"[{idx}/{total}] ✓ Sent to {phone}")
                else:
                    r.status = 'failed'
                    current_progress['failure_count'] += 1
                    current_progress['logs'].append(f"[{idx}/{total}] ✗ Failed for {phone}: {last_err}")

                db.session.commit()

                # update campaign counters incrementally (safe approach)
                campaign.sent_count = CampaignRecipient.query.filter_by(campaign_id=campaign_id, status='sent').count()
                campaign.failed_count = CampaignRecipient.query.filter_by(campaign_id=campaign_id, status='failed').count()
                db.session.commit()

                # human-like jitter
                time.sleep(int(getattr(whatsapp_sender, 'config', {}).get('delay_between_messages', 1.5)) + 0.3)

            # finalize campaign status if not cancelled
            if campaign.status != 'cancelled':
                sent = campaign.sent_count or 0
                failed = campaign.failed_count or 0
                if total == 0:
                    campaign.status = 'failed'
                elif sent == total:
                    campaign.status = 'completed'
                elif sent > 0:
                    campaign.status = 'partial_failed'
                else:
                    campaign.status = 'failed'
                campaign.updated_at = datetime.now()
                db.session.commit()

            # finalize current_progress
            current_progress['is_active'] = False
            current_progress['end_time'] = datetime.now().isoformat()
            current_progress['logs'].append(
                f"Campaign {campaign_id} finished. Sent: {campaign.sent_count}, Failed: {campaign.failed_count}"
            )

        except Exception as ex:
            current_app.logger.exception("Worker exception")
            current_progress['logs'].append(f"[ERROR] Worker exception: {str(ex)}")
            current_progress['is_active'] = False
            try:
                campaign = Campaign.query.get(campaign_id)
                if campaign:
                    campaign.status = 'failed'
                    db.session.commit()
            except Exception:
                pass

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
            print("file issue")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            print(" file issue 2")
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename, 'recipients'):
            print("123")
            return jsonify({'error': 'Invalid file format. Please upload Excel files only.'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Read Excel file
        df = pd.read_excel(filepath)
        print(df.head(1))
        # Validate columns
        required_columns = ['Name', 'Contact']
        missing_columns = [col for col in required_columns if col not in df.columns]
        print(missing_columns)
        if missing_columns:
            print("missing col")
            return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400
        
        added_customers = []
        errors = []
        print("congrats u came till here")

        for index, row in df.iterrows():
            try:
                name = str(row['Name']).strip()
                phone = str(row['Contact']).strip()
                email = str(row.get('Email', '')).strip() if pd.notna(row.get('Email')) else ''
                
                if not name or not phone:
                    errors.append(f'Row {index + 2}: Name and Phone are required')
                    continue
                
                # Check if customer already exists
                existing = Customer.query.filter_by(phone=phone).first()
                if existing:
                    errors.append(f'Row {index + 2}: Customer with phone {phone} already exists')
                    continue
                print("hi")
                customer = Customer(name=name, phone=phone, email=email)
                print("hi2")
                db.session.add(customer)
                print("")
                added_customers.append(customer)
                print("this is the end",add_customer)
                
            except Exception as e:
                print("here")
                print(e)
                errors.append(f'Row {index + 2}: {str(e)}')
        print("loop done")
        db.session.commit()
        
        # Clean up uploaded file
        #os.remove(filepath)
        
        return jsonify({
            'message': f'Successfully added {len(added_customers)} customers',
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to process file: {str(e)}'}), 500

# Campaign Management API Endpoints

def create_campaign(status=None):
    content_type = (request.content_type or '').lower()
    attachment_path = None
    recipients_list = []
    scheduled_date_str = None

    # --- Part 1: Get data from the request ---
        
    if content_type.startswith('multipart/form-data'):
        # Form-data request
        data = request.form
        name = data.get('name')
        message = data.get('message')
        description = data.get('description', '')
        file = request.files.get('attachment')
        scheduled_date_str = data.get('scheduled_date') 
        recipients_list = json.loads(data.get('recipients', '[]'))
        status = status or data.get('status') or ('scheduled' if scheduled_date_str else 'queued')
            
    else: # This path is for JSON requests like 'Save as Draft'
        data = request.get_json(force=True)
        name = data.get('name')
        message = data.get('message')
        description = data.get('description', '')
        status = status or data.get('status')
        recipients_list = data.get('recipients', [])
        file = None

    # --- Part 2: Validate the data ---

    if not name or not message:
        raise ValueError({'error': 'Campaign name and message are required'})

    if not recipients_list:
        raise ValueError({'error': 'Recipients list is required'})

    # ---Part 4: Save attachment (if provided)---
    
    # --- Part 3: Build the database objects (without committing) ---
    try:
        campaign = Campaign(
            name=name,
            description=description,
            message=message,
            status=status,
            created_at=datetime.now(),
            scheduled_at=datetime.fromisoformat(scheduled_date_str) if scheduled_date_str else None,
            attachment_path=attachment_path
        )
    except Exception as e:
        raise ValueError(f"Failed to create campaign: {str(e)}")

    db.session.add(campaign)
    db.session.flush()  # to get campaign ID before adding recipients

    for rid in recipients_list:
        cid = int(rid)
        cust = Customer.query.get(cid)
        if cust:
            cr = CampaignRecipient(
                campaign_id=campaign.id,
                customer_id=cid,
                status='pending',
                recipient_name=cust.name,  # <-- Add the customer's name
                recipient_phone=cust.phone  # <-- Add the customer's phone
            )
            db.session.add(cr)
    
    if file and file.filename != '':
        if not allowed_file(file.filename, 'attachments'):
            raise ValueError({'error': 'Attachment type not allowed'})
        
        filename = secure_filename(f"{campaign.id}_{file.filename}")
        saved_path = os.path.join(UPLOAD_FOLDER, filename)
        print("LOCATion were the files gets saved",saved_path)
        file.save(saved_path)
        if hasattr(campaign, 'attachment'):
            campaign.attachment = filename
        attachment_path=saved_path
            
    return campaign, attachment_path

def schedule_campaign_job(campaign_id, attachment_path):
    """Adds a campaign sending task to the scheduler's job list."""
    with app.app_context():
        campaign = Campaign.query.get(campaign_id)
        if not campaign or not campaign.scheduled_at:
            app.logger.warning(f"Could not schedule campaign {campaign_id}: Campaign not found or has no scheduled date.")
            return

        job_id = f'campaign__{campaign.id}'
        
        try:
            scheduler.add_job(
                id=job_id,
                func=process_campaign_async,
                trigger='date',
                run_date=campaign.scheduled_at,
                args=[campaign.id, attachment_path],
                replace_existing=True
            )
            # Log the successful scheduling of the job
            app.logger.info(f"Successfully scheduled campaign {campaign_id} with job ID {job_id} to run at {campaign.scheduled_at}.")
        except Exception as e:
            # Log any errors that occur during scheduling
            app.logger.error(f"Failed to schedule campaign {campaign_id}: {e}", exc_info=True)


@app.route('/api/campaigns/draft', methods=['POST'])
def save_campaign_draft():
    """API endpoints to ONLY save a campaign as a draft"""
    try:
        create_campaign('draft')
        db.session.commit()
        return jsonify({'message': 'Campaign draft saved successfully'}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Failed to save campaign draft")
        return jsonify({'error': f'Failed to save campaign draft: {str(e)}'}), 500

@app.route('/api/campaigns/send', methods=['POST'])
def send_campaign():
    """
    API endpoint to either queue a campaign for immediate sending 
    or schedule it for a future time.
    """
    try:
        print("1.",request.form)
        status_from_request = request.form.get('status', 'queued')
        campaign, attachment_path = create_campaign(status_from_request)
        print("2.",campaign,"ATTACHMENT PATH:",attachment_path)
        db.session.commit()

        if campaign.status == 'queued':
            thread = threading.Thread(target=process_campaign_async, args=(campaign.id, attachment_path))
            thread.daemon = True
            thread.start()
        elif campaign.status == 'scheduled':
            # ADD THIS: Use the scheduler for 'scheduled' status
            schedule_campaign_job(campaign.id, attachment_path)

        return jsonify({'message': 'Campaign sent successfully', 'campaign': campaign.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Failed to send campaign")
        return jsonify({'error': f'Failed to send campaign: {str(e)}'}), 500


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
    

@app.route('/api/campaigns/<int:campaign_id>/duplicate', methods=['GET'])
def duplicate_campaign(campaign_id):
    """Retrive a single campaign DATA"""
    try:
        original = Campaign.query.get_or_404(campaign_id)
        print("this is duplicates data",original)
        return jsonify(original.to_dict()),200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to duplicate campaign: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/cancel', methods=['POST'])
def cancel_campaign(campaign_id):
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        # only allow cancel when queued or running
        if campaign.status not in ('queued', 'running', 'scheduled'):
            return jsonify({'error': f'Cannot cancel campaign in state {campaign.status}'}), 400
        campaign.status = 'cancel_requested'
        db.session.commit()
        return jsonify({'message': 'Cancel requested'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to request cancel: {str(e)}'}), 500
    
@app.route('/api/scheduler/jobs', methods=['GET']) #campaign schedule job endpoints
def list_scheduled_jobs():
    """An endpoint to view all currently scheduled jobs."""
    jobs_list = []
    for job in scheduler.get_jobs():
        jobs_list.append({
            'id': job.id,
            'name': job.name,
            'trigger': str(job.trigger),
            'next_run_time': str(job.next_run_time)
        })
    return jsonify(jobs=jobs_list)

# QR Code API
@app.route('/api/whatsapp/qr', methods=['GET'])
def get_qr_code():
    """Get QR code from WhatsApp Web, keeping the browser session alive."""
    global whatsapp_sender
    print("api call for qr code")

    try:
        # Initialize sender if it doesn't exist or driver is not running
        if whatsapp_sender is None or not whatsapp_sender.is_driver_active():
            whatsapp_sender = WhatsAppBulkSenderAPI()
            whatsapp_sender.initialize_driver()
            print("Chrome WebDriver initialized successfully for QR capture")

        # Capture QR code
        qr_result = whatsapp_sender.capture_qr_code()

        if qr_result == "already_connected":
            print("WhatsApp Web already connected")
            return jsonify({
                'success': True,
                'already_connected': True,
                'message': 'WhatsApp Web is already connected.',
                'timestamp': datetime.now().isoformat()
            })
        elif qr_result:
            print("QR code captured successfully")
            # The browser is intentionally left open for the user to scan
            return jsonify({
                'success': True,
                'qr_code': qr_result,
                'message': 'Scan the QR code in the new browser window.',
                'timestamp': datetime.now().isoformat()
            })
        else:
            print("QR code capture failed")
            return jsonify({
                'success': False,
                'message': 'Could not capture QR code. Please try again.',
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        print(f"Error in get_qr_code: {str(e)}")
        # Ensure driver is closed on failure
        if whatsapp_sender:
            whatsapp_sender.quit_driver()
            whatsapp_sender = None
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}',
            'timestamp': datetime.now().isoformat()
        })

# WhatsApp Connection API
@app.route('/api/whatsapp/status', methods=['GET'])
def get_whatsapp_status():
    """Check WhatsApp connection status using the global sender instance."""
    global whatsapp_sender
    if whatsapp_sender is None or not whatsapp_sender.is_driver_active():
        # whatsapp_sender = WhatsAppBulkSenderAPI()
        # whatsapp_sender.initialize_driver()
        # print("\n\\n\n\n\n\Chrome WebDriver initialized successfully (in status api)\n\n\n\n")

        print("this is the error")
        return jsonify({
            'connected': False,
            'status': 'disconnected',
            'message': 'Not connected. Please get QR code first.',
            'timestamp': datetime.now().isoformat()
        })

    try:
        if whatsapp_sender.get_connection_status():
            status = {
                'connected': True,
                'status': 'connected',
                'message': 'WhatsApp is connected and ready.',
                'timestamp': datetime.now().isoformat()
            }
        else:
            status = {
                'connected': False,
                'status': 'qr_required',
                'message': 'QR code scan required to connect',
                'timestamp': datetime.now().isoformat()
            }
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
        pending_customers = Customer.query.filter_by(status='Pending').count()
        
        # Get recent campaigns
        recent_campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()
        
        analytics_data = {
            'total_customers': total_customers,
            'opted_in_customers': opted_in_customers,

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

#upadteing profile vasl
@app.route('/api/settings/profile', methods=['POST'])
def update_settings_profile():
    """
    Updates the settings by writing the changes to config.py.
    """
    try:
        data = request.get_json()
        
        user_data_dir = data.get('user_data_dir')
        profile_name = data.get('profile_name')
        
        if not user_data_dir or not profile_name:
            return jsonify({'error': 'Missing user_data_dir or profile_name in request'}), 400

        # Path to the config file
        config_file_path = os.path.join(os.path.dirname(__file__), 'whatsapp_sender/config.py')

        # Read the current content of the config file
        with open(config_file_path, 'r') as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            # Replace the old 'user_data_dir' line with the new value
            if line.strip().startswith("'user_data_dir':"):
                new_lines.append(f"    'user_data_dir': os.getenv('CHROME_USER_DATA_DIR', r'{user_data_dir}'),\n")
            # Replace the old 'profile_name' line with the new value
            elif line.strip().startswith("'profile_name':"):
                new_lines.append(f"    'profile_name': os.getenv('CHROME_PROFILE_NAME', '{profile_name}'),\n")
            else:
                new_lines.append(line)

        # Write the updated content back to the file
        with open(config_file_path, 'w') as f:
            f.writelines(new_lines)
            
        # Optional: Reload the config in memory for the current session
        # This part depends on how your app is structured. 
        # For simplicity, we'll assume the app is restarted or the config is reloaded on next request.
            
        return jsonify({'message': 'Settings updated and saved successfully'}), 200

    except Exception as e:
        print(f"Error updating and saving settings: {e}")
        return jsonify({'error': 'Failed to update settings permanently'}), 500

#updating webdrive(selenium) vals
@app.route('/api/settings/websettings', methods=['POST'])
def update_settings_webdriver():
    """
    Updates the settings by writing the changes to config.py.
    """
    try:
        data = request.get_json()
        
        max_retries = data.get('max_retries')
        delay_between_messages = data.get('delay_between_messages')
        upload_timeout = data.get('upload_timeout')
        chat_load_timeout = data.get('chat_load_timeout')
        
        if not chat_load_timeout or not upload_timeout or not max_retries or not delay_between_messages:
            return jsonify({'error': 'Missing user_data_dir or profile_name in request'}), 400

        # Path to the config file
        config_file_path = os.path.join(os.path.dirname(__file__), 'whatsapp_sender/config.py')

        # Read the current content of the config file
        with open(config_file_path, 'r') as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            # Replace the old 'user_data_dir' line with the new value
            if line.strip().startswith("'max_retries':"):
                new_lines.append(f"    'max_retries': os.getenv('CHROME_USER_DATA_DIR', r'{max_retries}'),\n")
            # Replace the old 'profile_name' line with the new value
            elif line.strip().startswith("'delay_between_messages':"):
                new_lines.append(f"    'delay_between_messages': os.getenv('CHROME_PROFILE_NAME', '{delay_between_messages}'),\n")
            elif line.strip().startswith("'upload_timeout':"):
                new_lines.append(f"    'upload_timeout': os.getenv('CHROME_PROFILE_NAME', '{upload_timeout}'),\n")
            elif line.strip().startswith("'chat_load_timeout':"):
                new_lines.append(f"    'chat_load_timeout': os.getenv('CHROME_PROFILE_NAME', '{chat_load_timeout}'),\n")
            else:
                new_lines.append(line)

        # Write the updated content back to the file
        with open(config_file_path, 'w') as f:
            f.writelines(new_lines)
            
        # Optional: Reload the config in memory for the current session
        # This part depends on how your app is structured. 
        # For simplicity, we'll assume the app is restarted or the config is reloaded on next request.
            
        return jsonify({'message': 'Settings updated and saved successfully'}), 200

    except Exception as e:
        print(f"Error updating and saving settings: {e}")
        return jsonify({'error': 'Failed to update settings permanently'}), 500
    
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
