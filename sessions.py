# sessions.py — full replacement
from db import get_client
import os
from datetime import datetime, timedelta
import pytz

supabase = get_client()

IST = pytz.timezone("Asia/Kolkata")


def _today_ist_iso() -> str:
    """Return today's IST date as YYYY-MM-DD."""
    return datetime.now(IST).strftime("%Y-%m-%d")


MAX_HISTORY_MESSAGES = 20

# Every message is stored with the time it was sent (agent.py stamps it) and
# Ace sees that time, so an old "booked for today" reads as old. Past a week
# the context is more likely to mislead than help, so it is dropped.
MAX_HISTORY_AGE = timedelta(days=7)


def _parse_ts(value):
    """Stored ISO timestamp -> aware datetime, or None if missing/unreadable."""
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return IST.localize(ts) if ts.tzinfo is None else ts


def get_session(phone: str) -> list:
    """Return the conversation history Ace should see for this message.

    Keeps the last MAX_HISTORY_MESSAGES messages from the past week. Messages
    saved before timestamps existed carry no time, so they are kept only on
    the day they were written (session_date) and dropped after that: shown
    undated on a later day they are what made Ace mistake a correct
    confirmation from yesterday for a contradiction. Old "Date has changed"
    system notes are dropped too; message times replace them.
    """
    today = _today_ist_iso()

    result = (
        supabase.table("sessions")
        .select("history, session_date")
        .eq("phone", phone)
        .execute()
    )
    if not result.data:
        return []

    row = result.data[0]
    history = row.get("history") or []
    same_day = row.get("session_date") == today
    cutoff = datetime.now(IST) - MAX_HISTORY_AGE

    kept = []
    for msg in history:
        if msg.get("role") == "system":
            continue
        ts = _parse_ts(msg.get("ts"))
        if ts is None:
            if same_day:
                kept.append(msg)
        elif ts >= cutoff:
            kept.append(msg)

    if len(kept) != len(history):
        print(f"[get_session] {phone}: dropped {len(history) - len(kept)} old or undated messages")
    return kept[-MAX_HISTORY_MESSAGES:]


def update_session(phone: str, history: list):
    """Persist history and stamp session_date to today's IST date.

    Falls back to a history-only upsert if the session_date column hasn't been
    added yet (migration pending in Supabase SQL editor).
    """
    payload = {
        "phone": phone,
        "history": history,
        "session_date": _today_ist_iso(),
        "updated_at": "NOW()"
    }
    try:
        supabase.table("sessions").upsert(payload).execute()
    except Exception:
        # session_date column missing — retry without it
        payload.pop("session_date", None)
        supabase.table("sessions").upsert(payload).execute()


def is_admin_mode(phone: str) -> bool:
    result = supabase.table("sessions").select("is_admin").eq("phone", phone).execute()
    return result.data[0].get("is_admin", False) if result.data else False


def set_admin_mode(phone: str, value: bool):
    supabase.table("sessions").upsert({
        "phone": phone,
        "is_admin": value,
        "updated_at": "NOW()"
    }).execute()
