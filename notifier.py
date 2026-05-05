import requests
import config
import csv
from datetime import datetime

def send_telegram_msg(message, symbol="NIFTY", pattern="UNKNOWN"):
    """Sends a Telegram message and logs the hit to alerts.csv."""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    # 1. Send to Telegram
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

    # 2. Log to CSV (The "History" part)
    try:
        with open('alert.csv', mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Log columns: Time, Symbol, Pattern Name, Message
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                symbol, 
                pattern, 
                message.replace('\n', ' ')
            ])
    except Exception as e:
        print(f"❌ CSV Logging Error: {e}")