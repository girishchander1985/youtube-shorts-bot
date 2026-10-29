import os
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_alert(video_title: str, video_id: str, topic_summary: str = None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram keys missing. Skipping alert.")
        return
    message = (
        "🚀 *YouTube Short Published!*\n\n"
        f"🎬 *Title:* {video_title}\n"
        f"📝 *Topic:* {topic_summary}\n\n"
        f"🔗 [Watch Short](https://youtube.com/shorts/{video_id})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)

def send_telegram_error(error_msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": f"⚠️ *Bot Failure Alert!*\n\n`{error_msg}`", "parse_mode": "Markdown"}, timeout=10)