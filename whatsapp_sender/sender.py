import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from datetime import datetime
from .config import CONFIG

class WhatsAppBulkSender:
    def __init__(self):
        self.driver = None
        self.config = CONFIG
        self.stats = {
            'success': 0,
            'failures': 0,
            'start_time': None,
            'end_time': None
        }

    def initialize_driver(self):
        print("Initializing Chrome with existing profile...")
        options = webdriver.ChromeOptions()
        
        # Add existing profile configuration
        user_data_dir = self.config.get('user_data_dir', '')
        profile_name = self.config.get('profile_name', '')
        
        if user_data_dir:
            profile_path = os.path.join(user_data_dir, profile_name) if profile_name else user_data_dir
            options.add_argument(f'--user-data-dir={profile_path}')
            print(f"Using Chrome profile: {profile_path}")
        
        # Existing performance options
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--log-level=3')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        print("Chrome WebDriver initialized with persistent session support.")

    def login_to_whatsapp(self):
        if not self.driver:
            print("WebDriver not initialized")
            return False
            
        print("Checking existing WhatsApp session...")
        self.driver.get('https://web.whatsapp.com')
        
        # Check if already logged in
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//div[@id="pane-side"]'))
            )
            print("Using existing WhatsApp session")
            return True
        except TimeoutException:
            print("Session not found - manual QR scan required")
        
        # Original QR scan flow
        print("Please scan QR code. Waiting 2 minutes...")
        try:
            WebDriverWait(self.driver, 120).until(
                EC.presence_of_element_located((By.ID, 'pane-side'))
            )
            print("Login successful via QR scan")
            return True
        except TimeoutException:
            print("Login timed out. Please try again.")
            return False

    def load_recipient_data(self, file_path):
        print(f"Loading recipient data from {file_path}...")
        try:
            xls = pd.ExcelFile(file_path)
            sheet_names = xls.sheet_names
            print(f"Found sheets: {sheet_names}")

            df = pd.read_excel(file_path, sheet_name=sheet_names[0])
            contact_column = next((col for col in df.columns if col.strip().lower() == 'contact'), None)
            if contact_column is None:
                if df.shape[1] > 1:
                    print("No 'Contact' column found. Using second column for contact numbers.")
                    df.rename(columns={df.columns[1]: 'Contact'}, inplace=True)
                elif df.shape[1] > 0:
                    print("Only one column found. Using first column for contact numbers.")
                    df.rename(columns={df.columns[0]: 'Contact'}, inplace=True)
                else:
                    raise ValueError("Excel sheet is empty or has no columns.")

            df.rename(columns={contact_column: 'Contact'}, inplace=True)
            df['Contact'] = df['Contact'].astype(str).str.replace(r'\D', '', regex=True)

            if 'Message' not in df.columns:
                df['Message'] = ''
            print(f"Successfully loaded {len(df)} recipients.")
            df['Message'] = df['Message'].fillna('').astype(str)
            return df
        except Exception as e:
            print(f"Error loading recipient data: {str(e)}")
            raise

    def send_message(self, contact, message, attachment_path=None):
        if not self.driver:
            print("WebDriver not initialized")
            return False
            
        print(f"Attempting to send message to {contact}...")
        try:
            print(f"Opening chat with {contact}...")
            self.driver.get(f'https://web.whatsapp.com/send?phone={contact}')
            wait = WebDriverWait(self.driver, self.config['chat_load_timeout'])
            try:
                WebDriverWait(self.driver, 15).until(EC.any_of(
                    EC.presence_of_element_located((By.XPATH, '//div[@role="textbox" and @contenteditable="true" and @aria-label="Type a message"]')),
                    EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "not on WhatsApp")]'))
                ))
            except TimeoutException:
                print("Chat loading timed out, proceeding anyway")
            invalid_number = self.driver.find_elements(By.XPATH, '//div[contains(text(), "not on WhatsApp")]')
            if invalid_number:
                print(f"Error: {contact} is not registered on WhatsApp")
                return False
            try:
                input_box = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@role="textbox" and @contenteditable="true" and @aria-label="Type a message"]')
                ))
            except TimeoutException:
                print("Error: Could not find message input area")
                return False
            if attachment_path:
                if not self._send_attachment(attachment_path, message):
                    return False
            elif message:
                if not self._send_text_message(message):
                    return False
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//span[@aria-label=" Delivered " and @data-icon="msg-dblcheck"]'))
                )
                print(f"✓ Message sent successfully to {contact}")
                return True
            except TimeoutException:
                print("Warning: Message send confirmation not detected")
                return True

        except Exception as e:
            print(f"Critical error sending to {contact}: {str(e)}")
            return False

    def _send_attachment(self, file_path, caption):
        if not self.driver:
            print("WebDriver not initialized")
            return False
            
        try:
            clip_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@title="Attach" and @type="button"]'))
            )
            clip_btn.click()

            file_input = self.driver.find_element(By.XPATH, '//input[@accept="*"]')
            file_input.send_keys(os.path.abspath(file_path))
            try:
                WebDriverWait(self.driver, self.config['upload_timeout']).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='button' and @aria-label='Send']"))
                )
            except TimeoutException:
                print("Error: Attachment upload took too long")
                self.driver.find_element(By.XPATH,'//div[@role="button" and @aria-label="Close"]').click()
                print("Attachment upload cancelled")
                return False
            
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ('.jpg', '.jpeg', '.png', '.gif', '.mp4','.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt') and caption:
                caption_box = self.driver.find_element(
                    By.XPATH, '//div[@role="textbox" and @contenteditable="true" and @aria-label="Add a caption"]')
                caption_box.send_keys(caption)

            send_btn = self.driver.find_element(By.XPATH,"//div[@role='button' and @aria-label='Send']")
            send_btn.click()
            time.sleep(self.config['delay_between_messages'])
            return True

        except Exception as e:
            print("Attachment sending failed")
            print(f"Attachment error: {str(e)}")
            return False

    def _send_text_message(self, message):
        if not self.driver:
            print("WebDriver not initialized")
            return False
            
        try:
            text_box = self.driver.find_element(
                By.XPATH, '//div[@role="textbox" and @contenteditable="true" and @aria-label="Type a message"]')

            text_box.send_keys(Keys.CONTROL + "a")
            text_box.send_keys(Keys.DELETE)

            lines = message.split('\n')
            for line in lines[:-1]:
                text_box.send_keys(line)
                text_box.send_keys(Keys.SHIFT + Keys.ENTER)
            text_box.send_keys(lines[-1])
            text_box.send_keys(Keys.ENTER)
            time.sleep(self.config['delay_between_messages'])
            return True

        except Exception as e:
            print(f"Text sending error: {str(e)}")
            return False

    def process_recipients(self, recipients, attachment_path=None):
        self.stats['start_time'] = datetime.now()
        print("\nStarting to process recipients...")

        for i, row in recipients.iterrows():
            contact = row['Contact']
            message = row['Message']
            print(f"\nProcessing recipient {i+1}/{len(recipients)}: {contact}")

            success = False
            for attempt in range(self.config['max_retries']):
                try:
                    if self.send_message(contact, message, attachment_path):
                        success = True
                        self.stats['success'] += 1
                        break
                except Exception as e:
                    time.sleep(2)

            if not success:
                self.stats['failures'] += 1

            time.sleep(self.config['delay_between_messages'])

        self.stats['end_time'] = datetime.now()
        self._generate_report()

    def _generate_report(self):
        duration = self.stats['end_time'] - self.stats['start_time']
        report = (
            "\n=== WhatsApp Bulk Sender Report ==="
            f"\nStart Time: {self.stats['start_time']}"
            f"\nEnd Time: {self.stats['end_time']}"
            f"\nDuration: {duration}"
            f"\nContacts Processed: {self.stats['success'] + self.stats['failures']}"
            f"\nSuccessful: {self.stats['success']}"
            f"\nFailed: {self.stats['failures']}"
            "\n==================================="
        )
        print(report)

    def run(self):
        try:
            print("=== WhatsApp Bulk Sender ===")
            excel_path = input("Enter path to Excel file: ").strip()
            attachment_path = input("Enter attachment path (optional): ").strip() or None

            if attachment_path and not os.path.exists(attachment_path):
                print(f"File not found: {attachment_path}")
                return

            self.initialize_driver()
            self.login_to_whatsapp()
            recipients = self.load_recipient_data(excel_path)
            self.process_recipients(recipients, attachment_path)
        except Exception as e:
            print(f"Critical error: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
                print("WebDriver closed. Exiting.")
