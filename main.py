from fastapi import FastAPI, Form, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import Response
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv
from agent import run_agent, run_admin_agent
from sessions import get_session, update_session, is_admin_mode, set_admin_mode
from reminders import run_booking_reminders
import os
from tools import normalize_phone
from supabase import create_client


load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

app = FastAPI()
twilio_client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
TWILIO_NUMBER = os.environ["TWILIO_WHATSAPP_NUMBER"]
ADMIN_PHONE = normalize_phone(os.getenv("ADMIN_PHONE", "")).replace("+91", "").replace(" ", "")
CRON_SECRET = os.getenv("CRON_SECRET", "")

TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
_twilio_validator = RequestValidator(TWILIO_AUTH_TOKEN)

# Set this when the proxy rewrites the Host header (Railway usually does not).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")


def _public_url(request: Request) -> str:
    """Rebuild the URL exactly as Twilio saw it when it signed the request.

    TLS terminates at the platform proxy, so request.url.scheme is http here
    while Twilio signed the https URL. Signature validation fails unless the
    forwarded proto is honoured.
    """
    if PUBLIC_BASE_URL:
        base = f"{PUBLIC_BASE_URL}{request.url.path}"
    else:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        base = f"{proto}://{host}{request.url.path}"
    return f"{base}?{request.url.query}" if request.url.query else base


def _require_twilio_signature(request: Request, form) -> None:
    """Reject anything that is not a genuine, unmodified Twilio request.

    Without this, anyone who learns the URL can POST an arbitrary From and Body
    and drive the agent as any customer -- including the admin number.
    """
    signature = request.headers.get("X-Twilio-Signature", "")
    url = _public_url(request)
    params = {k: v for k, v in form.items() if isinstance(v, str)}
    if not _twilio_validator.validate(url, params, signature):
        print(f"[SECURITY] Rejected request with bad/missing Twilio signature url={url}")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")



def _send_whatsapp(sender: str, reply) -> None:
    """Normalise the reply and send it, honouring [SPLIT] markers."""
    if isinstance(reply, list):
        reply = "\n".join(str(item) for item in reply)
    elif not isinstance(reply, str):
        reply = str(reply)

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


def _build_reply(user_message: str, sender: str, phone: str) -> str:
    """Work out what Ace should say. May raise; the caller handles that."""
    clean_phone = phone.replace("+91", "").replace(" ", "")

    # -- Admin login/logout intercept --------------------------------------
    if user_message.strip().lower() in ["admin login", "login admin"]:
        if clean_phone == ADMIN_PHONE:
            set_admin_mode(sender, True)
            return "\U0001F510 Admin mode activated. Welcome back, boss!"
        return "\u26D4 Unauthorized. This number is not registered as an admin."

    if user_message.strip().lower() in ["admin logout", "logout admin", "logout"]:
        set_admin_mode(sender, False)
        return "\u2705 Logged out of admin mode. You're now in customer mode."

    # -- Route based on current session mode -------------------------------
    history = get_session(sender)

    if is_admin_mode(sender):
        reply, updated_history = run_admin_agent(phone, user_message, history)
    else:
        reply, updated_history = run_agent(phone, user_message, history)

    update_session(sender, updated_history)
    return reply


async def process_message(user_message: str, sender: str, phone: str):
    """Runs in background -- no Twilio timeout risk.

    Everything that can fail (session load, RAG, the agent, session save) is
    inside the try. A background task that raises sends nothing at all, so the
    customer would sit there with no reply and no error.
    """
    try:
        reply = _build_reply(user_message, sender, phone)
    except Exception as e:
        print(f"[process_message error] {type(e).__name__}: {e}")
        reply = (
            "Sorry, I'm having a little trouble right now. "
            "Please try again in a moment! \U0001F64F"
        )

    _send_whatsapp(sender, reply)



@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """Responds to Twilio instantly, processes in background."""
    form = await request.form()
    _require_twilio_signature(request, form)

    sender = form.get("From") or ""
    body = (form.get("Body") or "").strip()
    if not sender:
        raise HTTPException(status_code=400, detail="Missing From")

    raw_phone = sender.replace("whatsapp:", "")
    phone = normalize_phone(raw_phone)
    background_tasks.add_task(process_message, body, sender, phone)
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
async def twilio_status_callback(request: Request):
    form = await request.form()
    _require_twilio_signature(request, form)

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