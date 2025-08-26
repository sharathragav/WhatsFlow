# WhatsApp Bulk Messaging Platform - Setup Instructions

## Overview
This guide covers setting up both the frontend (web interface) and backend (Flask API + WhatsApp automation) for local development with full functionality.

## Prerequisites

### System Requirements
- **Operating System**: Windows 10/11, macOS, or Linux
- **Python**: 3.11 or higher
- **Google Chrome**: Latest version installed
- **Internet Connection**: For WhatsApp Web and dependencies

### Check Your System
```bash
# Check Python version
python --version
# Should show Python 3.11.x or higher

# Check if Chrome is installed
google-chrome --version  # Linux
# or check in Applications (macOS) or Programs (Windows)
```

## Installation Steps

### Step 1: Download Project Files
```bash
# Download all project files to your local machine
# Essential files needed:
# - app.py, main.py
# - templates/, static/, whatsapp_sender/
# - pyproject.toml
# - All HTML, CSS, JS files
```

### Step 2: Create Virtual Environment
```bash
# Navigate to project directory
cd your-project-folder

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
# Option 1: From pyproject.toml (recommended)
pip install -e .

# Option 2: Manual installation
pip install flask>=3.1.1 pandas>=2.3.1 selenium>=4.34.2 webdriver-manager>=4.0.2 openpyxl>=3.1.5 xlrd>=2.0.2 pillow>=11.3.0 flask-cors>=6.0.1 werkzeug>=3.1.3 flask-migrate>=4.1.0 psycopg2-binary>=2.9.10 gunicorn>=23.0.0 email-validator>=2.2.0

# Verify installation
pip list
```

### Step 4: Configure Chrome Profile Settings
```bash
# Edit whatsapp_sender/config.py
# Update these paths for your system:

# Windows example:
'user_data_dir': r'C:\Users\YourUsername\AppData\Local\Google\Chrome\User Data'
'profile_name': 'Default'  # or your profile name

# macOS example:
'user_data_dir': '/Users/YourUsername/Library/Application Support/Google/Chrome'
'profile_name': 'Default'

# Linux example:
'user_data_dir': '/home/YourUsername/.config/google-chrome'
'profile_name': 'Default'
```

### Step 5: Create Required Directories
```bash
# Create upload directory
mkdir uploads

# Set permissions (Linux/macOS)
chmod 755 uploads
```

## Running the Application

### Backend (Flask Server)
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Start the Flask server
python main.py

# Alternative: Use Gunicorn (production-like)
gunicorn --bind 0.0.0.0:5000 --reload main:app
```

### Frontend Access
```bash
# Once backend is running, access the web interface:
# Local URL: http://localhost:5000
# Or: http://127.0.0.1:5000

# The application includes:
# ✅ Dashboard - Overview and quick actions
# ✅ Customers - Contact management
# ✅ Campaigns - Message campaign creation
# ✅ WhatsApp - Bulk message sending
# ✅ Settings - Configuration management
```

## WhatsApp Web Setup

### Step 1: Login to WhatsApp Web
```bash
# 1. Open Chrome browser
# 2. Go to https://web.whatsapp.com
# 3. Scan QR code with your phone
# 4. Ensure "Keep me signed in" is checked
# 5. Verify your profile name in Chrome settings
```

### Step 2: Test WhatsApp Connection
```bash
# 1. Go to Settings page in the application
# 2. Verify Chrome profile settings
# 3. Click "Test Profile" button
# 4. Check if WhatsApp Web loads automatically
```

## Project Structure

### Frontend Files
```
templates/
├── base.html          # Main layout template
├── dashboard.html     # Main dashboard
├── customers.html     # Customer management
├── campaigns.html     # Campaign creation
├── whatsapp.html      # Bulk messaging interface
└── settings.html      # Configuration

static/
├── css/
│   └── whatsapp-theme.css  # Main stylesheet
└── js/
    └── dashboard.js        # JavaScript functionality
```

### Backend Files
```
app.py                 # Main Flask application
main.py               # Application entry point
whatsapp_sender/
├── __init__.py       # Package initialization
├── config.py         # Configuration settings
└── sender.py         # WhatsApp automation logic
```

## Configuration Options

### Environment Variables (Optional)
```bash
# Set environment variables to override defaults
export CHROME_USER_DATA_DIR="/path/to/chrome/data"
export CHROME_PROFILE_NAME="YourProfileName"
export SESSION_SECRET="your-secret-key"

# Windows Command Prompt:
set CHROME_USER_DATA_DIR=C:\path\to\chrome\data
set CHROME_PROFILE_NAME=YourProfileName
set SESSION_SECRET=your-secret-key
```

### Application Settings
```python
# Edit whatsapp_sender/config.py to modify:
CONFIG = {
    'max_retries': 3,                    # Message retry attempts
    'delay_between_messages': 10,        # Seconds between messages
    'upload_timeout': 60,                # File upload timeout
    'chat_load_timeout': 45,             # Chat loading timeout
    'max_file_size': 16 * 1024 * 1024,   # 16MB file size limit
    'log_level': 'INFO'                  # Logging verbosity
}
```

## Testing the Setup

### Step 1: Basic Functionality Test
```bash
# 1. Start the application: python main.py
# 2. Open browser: http://localhost:5000
# 3. Navigate through all 7 dashboards
# 4. Upload a test Excel file in Customers section
# 5. Create a test campaign
# 6. Check Settings page loads correctly
```

### Step 2: WhatsApp Automation Test
```bash
# 1. Go to WhatsApp section
# 2. Upload contact list (Excel file)
# 3. Enter test message
# 4. Start small test batch (2-3 contacts)
# 5. Monitor Progress page for real-time updates
# 6. Check Analytics for completion statistics
```

## Troubleshooting

### Common Issues

#### Chrome Profile Issues
```bash
# Problem: Chrome profile not found
# Solution: Update paths in whatsapp_sender/config.py
# Find your Chrome profile:
# Windows: C:\Users\[username]\AppData\Local\Google\Chrome\User Data
# macOS: ~/Library/Application Support/Google/Chrome
# Linux: ~/.config/google-chrome
```

#### WhatsApp Web Connection
```bash
# Problem: Can't connect to WhatsApp Web
# Solution: 
# 1. Clear Chrome cache and cookies
# 2. Re-login to WhatsApp Web manually
# 3. Check Chrome profile permissions
# 4. Verify internet connection
```

#### Python Dependencies
```bash
# Problem: Package installation fails
# Solution:
pip install --upgrade pip
pip install wheel setuptools
# Then retry package installation
```

#### Port Already in Use
```bash
# Problem: Port 5000 already occupied
# Solution: Kill existing process or use different port
# Kill process:
sudo lsof -t -i tcp:5000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :5000              # Windows

# Use different port:
python main.py --port 5001
```

## Performance Optimization

### For Better Performance
```bash
# 1. Close unnecessary Chrome tabs
# 2. Increase system RAM if possible
# 3. Use SSD storage for better file I/O
# 4. Adjust message delays based on your internet speed
# 5. Monitor system resources during bulk sending
```

### Recommended Settings
```python
# For stable bulk messaging:
'delay_between_messages': 15,  # Increased delay
'max_retries': 5,              # More retry attempts
'chat_load_timeout': 60,       # Longer timeout
```

## Security Considerations

### Data Protection
```bash
# 1. Keep customer data files secure
# 2. Use strong session secrets
# 3. Regular backup of important data
# 4. Don't share Chrome profiles
# 5. Monitor application logs
```

### Network Security
```bash
# 1. Use HTTPS in production
# 2. Configure firewall rules
# 3. Monitor network traffic
# 4. Regular security updates
```

## Production Deployment

### For Production Use
```bash
# 1. Use proper WSGI server (Gunicorn/uWSGI)
# 2. Set up reverse proxy (Nginx)
# 3. Configure SSL certificates
# 4. Set up monitoring and logging
# 5. Configure backup procedures

# Example production start:
gunicorn --workers 4 --bind 0.0.0.0:5000 main:app
```

## Support and Maintenance

### Regular Maintenance
- Update Chrome browser regularly
- Monitor application logs
- Backup customer data
- Update Python packages
- Clean upload directories

### Monitoring
- Check Chrome WebDriver compatibility
- Monitor WhatsApp Web session health
- Track message delivery rates
- Monitor system resource usage

---

**Note**: This application provides a complete WhatsApp bulk messaging solution with a modern web interface. The frontend and backend work together to provide customer management, campaign creation and real-time progress tracking.
