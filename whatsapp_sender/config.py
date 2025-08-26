import os

CONFIG = {
    # WebDriver settings
    'max_retries': os.getenv('CHROME_USER_DATA_DIR', r'3'),
    'delay_between_messages': os.getenv('CHROME_PROFILE_NAME', '30'),
    'upload_timeout': os.getenv('CHROME_PROFILE_NAME', '60'),
    'chat_load_timeout': os.getenv('CHROME_PROFILE_NAME', '50'),
    
    # Chrome profile settings (IMPORTANT: Update these paths)
    'user_data_dir': os.getenv('CHROME_USER_DATA_DIR', r'C:\Users\User\AppData\Local\Google\Chrome\User Data'),
    'profile_name': os.getenv('CHROME_PROFILE_NAME', 'Chrome_Profile'),
    
    # API settings
    'upload_folder': 'uploads',
    'max_file_size': int(os.getenv('MAX_FILE_SIZE_MB', '16')) * 1024 * 1024,
    # Logging
    'log_level': os.getenv('LOG_LEVEL', 'INFO'),
    'log_file': 'whatsapp_sender.log'
}

