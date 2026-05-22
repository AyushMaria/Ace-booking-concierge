from fastapi import FastAPI, Form, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import Response
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv
from agent import run_agent, run_admin_agent
from sessions import get_session, update_session, is_admin_mode, set_admin_mode
from reminders import run_booking_reminders
import os
import time
from threading import Lock
from tools import normalize_phone
from supabase import create_client


load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

app = FastAPI()
twilio_client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
TWILIO_NUMBER = os.environ["TWILIO_WHATSAPP_NUMBER"]
twilio_validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
ADMIN_PHONE = normalize_phone(os.getenv("ADMIN_PHONE", "")).replace("+91", "").replace(" ", "")
CRON_SECRET = os.getenv("CRON_SECRET", "")

RATE_LIMIT_SECONDS = 2
last_request_by_phone = {}
rate_limit_lock = Lock()


def allow_request(phone: str) -> bool:
    """Allow only 1 request per phone every RATE_LIMIT_SECONDS."""
    now = time.time()

    with rate_limit_lock:
        last_seen = last_request_by_phone.get(phone)

        if last_seen is not None and (now - last_seen) < RATE_LIMIT_SECONDS:
            return False

        last_request_by_phone[phone] = now
        return True


async def process_message(user_message: str, sender: str):
    """Runs in background — no Twilio timeout risk."""
    raw_phone = sender.replace("whatsapp:", "")
    phone = normalize_phone(raw_phone)
    clean_phone = phone.replace("+91", "").replace(" ", "")

    # ── Admin login/logout intercept ──────────────────────────
    if user_message.strip().lower() in ["admin login", "login admin"]:
        if clean_phone == ADMIN_PHONE:
            set_admin_mode(sender, True)
            reply = "🔐 Admin mode activated. Welcome back, boss!"
        else:
            reply = "⛔ Unauthorized. This number is not registered as an admin."

    elif user_message.strip().lower() in ["admin logout", "logout admin", "logout"]:
        set_admin_mode(sender, False)
        reply = "✅ Logged out of admin mode. You're now in customer mode."

    # ── Route based on current session mode ───────────────────
    else:
        history = get_session(sender)

        if is_admin_mode(sender):
            reply, updated_history = run_admin_agent(phone, user_message, history)
        else:
            reply, updated_history = run_agent(phone, user_message, history)

        update_session(sender, updated_history)

    # ── Send messages (split-aware) ───────────────────────────
    parts = [p.strip() for p in reply.split("[SPLIT]") if p.strip()]

    for part in parts:
        try:
            twilio_client.messages.create(
                from_=TWILIO_NUMBER,
                to=sender,
                body=part
            )
        except Exception as e:
            print(f"[ERROR] Failed to send message: {e}")


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    Body: str = Form(...),
    From: str = Form(...),
    x_twilio_signature: str = Header(default="", alias="X-Twilio-Signature")
):
    """Responds to Twilio instantly, processes in background."""
    form_data = await request.form()
    form_dict = dict(form_data)

    request_url = str(request.url)
    is_valid = twilio_validator.validate(request_url, form_dict, x_twilio_signature)

    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    sender = From.strip()
    rate_limit_key = normalize_phone(sender.replace("whatsapp:", ""))

    if not allow_request(rate_limit_key):
        return Response(content="", media_type="application/xml")

    background_tasks.add_task(process_message, Body.strip(), sender)
    return Response(content="", media_type="application/xml")


@app.post("/cron/send-booking-reminders")
def send_booking_reminders(x_cron_secret: str = Header(default="")):
    if not CRON_SECRET or x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = run_booking_reminders(window_start_mins=60, window_end_mins=120)
    return {
        "status": "ok",
        **result
    }


@app.post("/twilio/status-callback")
async def twilio_status_callback(
    request: Request,
    x_twilio_signature: str = Header(default="", alias="X-Twilio-Signature")
):
    form = await request.form()
    form_dict = dict(form)

    request_url = str(request.url)
    is_valid = twilio_validator.validate(request_url, form_dict, x_twilio_signature)

    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    message_sid = form.get("MessageSid")
    message_status = form.get("MessageStatus")
    error_code = form.get("ErrorCode")
    error_message = form.get("ChannelStatusMessage")

    print(
        f"[TWILIO_STATUS] sid={message_sid} "
        f"status={message_status} error_code={error_code} "
        f"error_message={error_message}"
    )

    supabase.table("outbound_messages").update({
        "final_status": message_status,
        "error_code": error_code,
        "error_message": error_message
    }).eq("twilio_sid", message_sid).execute()

    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "Ace is running 🎾"}