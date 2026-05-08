import requests
import config
import csv
from datetime import datetime
from wabridge import WABridge  # Import the WhatsApp bridge

# Initialize the WhatsApp connection
wa = WABridge()

def send_master_alert(message, symbol="NIFTY", pattern="UNKNOWN"):
    """The 'Master' function that coordinates all notifications."""
    
    # 1. Internal Log (CSV)
    log_to_csv(message, symbol, pattern)
    
    # 2. Call Telegram
    send_telegram(message)
    
    # 3. Call WhatsApp
    send_whatsapp(message)

def send_telegram(message):
    """Handles Telegram logic exclusively."""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def send_whatsapp(message):
    """Handles WhatsApp logic exclusively."""
    try:
        # Removes Markdown bold '*' for cleaner WhatsApp reading if desired
        clean_msg = message.replace("*", "") 
        wa.send(config.WHATSAPP_PHONE, clean_msg)
    except Exception as e:
        print(f"❌ WhatsApp Error: {e}")

def log_to_csv(message, symbol, pattern):
    """Records the hit in your local database."""
    try:
        with open('alert.csv', mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, pattern, message.replace('\n', ' ')])
    except Exception as e:
        print(f"❌ CSV Logging Error: {e}")