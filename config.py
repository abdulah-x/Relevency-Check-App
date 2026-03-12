import os
import sys
from datetime import timezone, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

PKT = timezone(timedelta(hours=5))

IMAP_HOST        = "imap.gmail.com"
IMAP_PORT        = 993
SMTP_SERVER      = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT        = int(os.getenv("SMTP_PORT", 587))
IMAP_EMAIL       = os.getenv("IMAP_EMAIL")          # inbox to watch (ahmedghazi495@gmail.com)
IMAP_PASSWORD    = os.getenv("IMAP_PASSWORD")        # app password for IMAP_EMAIL
SENDER_EMAIL     = os.getenv("SENDER_EMAIL")         # monitor's sender address
SENDER_PASSWORD  = os.getenv("SENDER_PASSWORD")      # app password for SENDER_EMAIL
RECIPIENT_EMAILS = [e.strip() for e in os.getenv("RECIPIENT_EMAILS", "").split(",") if e.strip()]
WATCH_FROM_EMAILS = [e.strip().lower() for e in os.getenv("WATCH_FROM_EMAILS", "").split(",") if e.strip()]
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MONGO_URI        = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MIN_SCORE        = int(os.getenv("MIN_SCORE", 70))
CHECK_INTERVAL   = int(os.getenv("CHECK_INTERVAL", 60))
IMAP_LOOKBACK_DAYS = int(os.getenv("IMAP_LOOKBACK_DAYS", 2))
MAX_EMAILS_PER_CHECK = int(os.getenv("MAX_EMAILS_PER_CHECK", 5))
SEND_TEST_EMAILS = os.getenv("SEND_TEST_EMAILS", "false").strip().lower() in ("1", "true", "yes", "y")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 10)) # Log heartbeat every X cycles

TEST_MODE   = "--test"  in sys.argv
CONSULTANTS = ["Brendi", "Claireee", "Jack", "Richu"]
