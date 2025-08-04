import os

CONFIG = {
    # WebDriver settings
    'max_retries': 3,
    'delay_between_messages': 10,  # seconds between messages
    'upload_timeout': 60,          # seconds for file upload
    'chat_load_timeout': 45,       # seconds to wait for chat to load
    
    # Chrome profile settings (IMPORTANT: Update these paths)
    'user_data_dir': os.getenv('CHROME_USER_DATA_DIR', r'C:\Users\shara\AppData\Local\Google\Chrome\User Data'),
    'profile_name': os.getenv('CHROME_PROFILE_NAME', 'Sharath Ragav'),
    
    # API settings
    'upload_folder': 'uploads',
    'max_file_size': 16 * 1024 * 1024,  # 16MB max file size
    
    # Logging
    'log_level': 'INFO',
    'log_file': 'whatsapp_sender.log'
}
