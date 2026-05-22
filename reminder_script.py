import httpx
import os
from dotenv import load_dotenv
from logging_config import get_logger

logger = get_logger(__name__)

load_dotenv()

CRON_SECRET = os.getenv("CRON_SECRET")
APP_URL = os.getenv("APP_URL")  # your Railway app URL e.g. https://ace-booking.up.railway.app

response = httpx.post(
    f"{APP_URL}/cron/send-booking-reminders",
    headers={"x-cron-secret": CRON_SECRET},
    timeout=30
)

logger.info("Reminder job completed", extra={"response": response.json()})