# sessions.py — full replacement
from supabase import create_client
import os
from datetime import datetime
import pytz

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])

IST = pytz.timezone("Asia/Kolkata")


def _today_ist_iso() -> str:
    """Return today's IST date as YYYY-MM-DD."""
    return datetime.now(IST).strftime("%Y-%m-%d")


def get_session(phone: str) -> list:
    """Return conversation history, annotating any cross-day rollover.

    If the stored session_date differs from today's IST date, a system note is
    prepended to the returned history so the model treats prior turns as
    prior-day context — not as a source for "today". The history array itself
    is never trimmed (preserves the personal touch across days).
    """
    today = _today_ist_iso()

    # Try the new schema (with session_date). Fall back to history-only if the
    # column hasn't been added yet (migration pending in Supabase SQL editor).
    try:
        result = (
            supabase.table("sessions")
            .select("history, session_date")
            .eq("phone", phone)
            .execute()
        )
    except Exception:
        result = (
            supabase.table("sessions")
            .select("history")
            .eq("phone", phone)
            .execute()
        )

    if not result.data:
        return []

    row = result.data[0]
    history = row.get("history") or []
    stored_date = row.get("session_date")

    # If session_date is missing or differs from today, annotate the rollover.
    # Skip the annotation only when stored_date == today (same-day continuation).
    if stored_date != today:
        note = {
            "role": "system",
            "content": (
                f"Date has changed: today is {today}. Treat any prior 'today' "
                f"references in this conversation as belonging to {stored_date or 'an earlier date'}, "
                f"not the current date. Use the system prompt's date as today."
            ),
        }
        # Prepend so it's the first thing the model sees this turn
        history = [note] + list(history)

    return history


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
