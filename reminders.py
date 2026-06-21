from datetime import datetime, timedelta
import os
import json
import pytz
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from supabase import create_client
from dotenv import load_dotenv
from tools import normalize_phone, parse_slots

load_dotenv()

ist = pytz.timezone("Asia/Kolkata")

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"]
)

TWILIO_NUMBER = os.environ["TWILIO_WHATSAPP_NUMBER"]
REMINDER_CONTENT_SID = os.environ["WHATSAPP_REMINDER_TEMPLATE_SID"]


def parse_slot_start(booking_date: str, slot_str: str) -> datetime:
    start_str = slot_str.split(" - ")[0].strip()
    dt = datetime.strptime(f"{booking_date} {start_str}", "%Y-%m-%d %I:%M %p")
    dt = ist.localize(dt)

    if start_str.endswith("AM") and start_str.startswith("12:"):
        dt += timedelta(days=1)

    return dt


def send_whatsapp_reminder(to_phone: str, name: str, date: str, slots: str) -> None:
    twilio_client.messages.create(
        from_=TWILIO_NUMBER,
        to=f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone,
        content_sid=REMINDER_CONTENT_SID,
        content_variables=json.dumps({"1": name, "2": date, "3": slots})
    )


def run_booking_reminders(window_start_mins: int = 60, window_end_mins: int = 120) -> dict:
    now = datetime.now(ist)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    result = supabase.table("bookings") \
        .select("id, name, phone, booking_date, slots, reminder_sent_at") \
        .neq("name", "BLOCKED") \
        .in_("booking_date", [today, tomorrow]) \
        .execute()

    checked = 0
    sent = 0
    skipped = 0
    errors = []

    for booking in result.data or []:
        checked += 1

        if booking.get("reminder_sent_at"):
            skipped += 1
            continue

        slots = parse_slots(booking["slots"])

        if not slots:
            skipped += 1
            continue

        first_slot = slots[0]
        slot_start = parse_slot_start(booking["booking_date"], first_slot)
        minutes_until = (slot_start - now).total_seconds() / 60

        if not (window_start_mins <= minutes_until <= window_end_mins):
            skipped += 1
            continue

        try:
            normalized_phone = normalize_phone(booking["phone"])
            send_whatsapp_reminder(
                to_phone=normalized_phone,
                name=booking["name"],
                date=booking["booking_date"],
                slots=", ".join(slots),
            )

            supabase.table("bookings") \
                .update({"reminder_sent_at": now.isoformat()}) \
                .eq("id", booking["id"]) \
                .execute()

            sent += 1

        except TwilioRestException as e:
            if e.code == 63016:
                errors.append(
                    f"Booking {booking['id']}: user has no WhatsApp session — "
                    f"send an opt-in template first"
                )
            else:
                errors.append(f"Booking {booking['id']}: {str(e)}")
        except Exception as e:
            errors.append(f"Booking {booking['id']}: {str(e)}")

    return {
        "checked": checked,
        "sent": sent,
        "skipped": skipped,
        "errors": errors
    }