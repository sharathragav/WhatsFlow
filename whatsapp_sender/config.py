import os

CONFIG = {
    # WebDriver settings
    'max_retries': os.getenv('MAX_RETRIES', r'3'),
    'delay_between_messages': os.getenv('DELAY_BETWEEN_MESSAGES', r'30'),
    'upload_timeout': os.getenv('UPLOAD_TIMEOUT', r'60'),
    'chat_load_timeout': os.getenv('CHAT_LOAD_TIMEOUT', r'50'),

    # Chrome profile settings (IMPORTANT: Update these paths)
    'user_data_dir': os.getenv('CHROME_USER_DATA_DIR', ''),
    'profile_name': os.getenv('CHROME_PROFILE_NAME', 'Default'),  
    
    # API settings
    'upload_folder': 'uploads',
    'max_file_size': int(os.getenv('MAX_FILE_SIZE_MB', '16')) * 1024 * 1024,
    # Logging
    'log_level': os.getenv('LOG_LEVEL', 'INFO'),
    'log_file': 'whatsapp_sender.log'
}
