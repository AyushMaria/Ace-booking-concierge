"""Venue knowledge for Ace: pricing, hours, policies and FAQs.

The knowledge base is eight short chunks, about 1,100 tokens in total. Ace used
to embed each incoming message with Gemini and pull the five nearest chunks
from pgvector. It now puts all of them in the system prompt instead: that
removes Ace's last dependency on Google, costs next to nothing once the prompt
is cached, and it was already fetching five of the eight on every message.
"""
import re
import time

from db import get_client
from dotenv import load_dotenv

load_dotenv()

supabase = get_client()

# Chunks change only when this file is re-seeded, so a short cache saves a
# Supabase round trip per message without serving stale knowledge for long.
_CACHE_TTL_SECONDS = 300
_cache = {"chunks": None, "loaded_at": 0.0}


def chunk_text(text: str, max_chars: int = 500) -> list[str]:
    paragraphs = re.split(r"\n{2,}", text)
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) > max_chars and current:
            chunks.append(current.strip())
            current = p
        else:
            current += "\n\n" + p
    if current.strip():
        chunks.append(current.strip())
    return chunks


def seed_knowledge(replace: bool = True):
    """Rewrite the knowledge base from the chunks below.

    The deployed app reads the chunks from Supabase, never from this file, so
    an edit here changes nothing until this runs: `python rag.py`.
    """
    knowledge = [
        {
            "category": "court_info",
            "text": (
                "Vibe & Volley Pickleball Courts by Tiny Tots Kindergarten, "
                "Chh. Sambhajinagar.\n"
                "Court operating hours: 7:00 AM–12:00 AM (continuous, no closure gap).\n"
                "Off-peak hours: 9:00 AM-5:00 PM.\n"
                "Peak hours: 7:00 AM-9:00 AM and 5:00 PM-12:00 AM.\n"
                "Last slot: 11:30 PM–12:00 AM.\n"
                "Contact: +919156156570."
            )
        },
        {
            "category": "pricing",
            "text": (
                "Standard price: ₹250 per 30-min slot (₹500/hour).\n"
                "Off-peak price (9:00 AM–5:00 PM): ₹150 per 30-min slot "
                "(₹300/hour).\n"
                "IMPORTANT: All slots are 30 minutes. 1 hour = 2 slots. "
                "Always quote and book in 30-min units. "
                "Example: '1 hour at 9 AM' = slots "
                "['9:00 AM - 9:30 AM', '9:30 AM - 10:00 AM'] = ₹300 total.\n"
                "Equipment (paddles and balls) is included in the court price. "
                "There is no rental charge and nothing to add on.\n"
                "Payment: Cash or UPI, collected after you play. No advance needed."
            )
        },
        {
            "category": "time_rules",
            "text": (
                "TIME DISAMBIGUATION RULES:\n"
                "RULE 1 — Numbers like '7', '8', '9', '10', '5', '6' could be "
                "AM or PM.\n"
                "RULE 2 — Same-day booking: compare against current IST time. "
                "If AM version has passed, assume PM. If both are future, ask. "
                "If AM is future but PM is outside hours, assume AM.\n"
                "RULE 3 — Future-date booking: always ask morning or evening, "
                "never assume.\n"
                "RULE 4 — Explicit AM/PM given: resolve immediately, no "
                "question.\n"
                "RULE 5 — '11' for today in evening → assume 11 PM. Never book "
                "past 12:00 AM. Never suggest a slot that already started."
            )
        },
        {
            "category": "date_rules",
            "text": (
                "DATE RULES:\n"
                "RULE 1 — Pass the customer's own words for the date to the "
                "tools ('tomorrow', 'this Saturday', 'next Monday', '17 Nov'). "
                "The tools work out the exact date; never calculate it yourself.\n"
                "RULE 2 — Before calling create_booking, read back the date the "
                "tool reports, as 'DD Mon YYYY', and wait for the customer to "
                "confirm. No booking on the same turn the date was given.\n"
                "RULE 3 — If a tool says it cannot read the date, ask the "
                "customer for the day and month, e.g. '17 Nov'.\n"
                "RULE 4 — Past dates are invalid. Ask for a future date.\n"
                "RULE 5 — If the date could be more than one day (e.g. "
                "'sometime next week'), ask for an exact date."
            )
        },
        {
            "category": "promo",
            "text": (
                "Promo code rules:\n"
                "- Never suggest, advertise, or proactively mention promo codes.\n"
                "- Apply only if the customer explicitly provides one.\n"
                "- Never auto-apply on the customer's behalf.\n"
                "- Always convert promo codes to UPPERCASE before passing to "
                "tools.\n"
                "- Pass the code to create_booking — the tool validates it "
                "against the database automatically."
            )
        },
                {
            "category": "booking_flow",
            "text": (
                "BOOKING FLOW:\n"
                "1. Silently call get_customer_by_phone before responding.\n"
                "2. Returning customer: greet by name, ask only for payment "
                "mode.\n"
                "3. New customer: ask Name | Payment mode.\n"
                "4. After create_booking succeeds: NEVER re-check availability. "
                "Treat as confirmed.\n"
                "5. After create_booking succeeds, send the confirmation and "
                "nothing else. Never upsell.\n"
                "6. If customer replies 'Ok', 'Fine', 'Sure', 'Alright' — "
                "treat as acceptance, do not re-ask.\n"
                "7. Payment must be Cash or UPI. If invalid, ask only for "
                "payment mode.\n"
                "8. Customer phone is from session — never ask for it, never "
                "display it unless explicitly asked.\n"
                "9. Call check_available_slots(date) to see all free slots — no time_block needed.\n"
                "SLOT MATH (non-negotiable): Every slot is 30 minutes. "
                "1 hour = 2 slots. 1.5 hours = 3 slots. 2 hours = 4 slots. "
                "Never pass a single slot string for a 1-hour booking. "
                "Always expand the customer's duration into the correct number "
                "of consecutive 30-min slot strings before calling create_booking."
            )
        },
        {
            "category": "equipment",
            "text": (
                "EQUIPMENT:\n"
                "- Paddles and balls are provided with every booking, included "
                "in the court price.\n"
                "- Premium paddle rental has been discontinued. Never offer it, "
                "never quote a rental price, and never raise it unprompted.\n"
                "- If a customer asks to rent a paddle, say rentals have ended "
                "but equipment comes with the court at no extra charge.\n"
                "- Customers are welcome to bring their own paddles.\n"
                "- Never upsell anything after a confirmation."
            )
        },
        {
            "category": "faq",
            "text": (
                "FAQ:\n"
                "Q: Can I bring my own paddle? A: Yes.\n"
                "Q: Is there parking? A: Yes, free parking at the venue.\n"
                "Q: How many courts? A: 1 pickleball court.\n"
                "Q: Can I book for someone else? A: Yes, provide their name, "
                "phone, email.\n"
                "Q: What if I'm late? A: Slot time is fixed, no extensions.\n"
                "Q: Do you rent paddles? A: No. Paddle rental has ended, but "
                "paddles and balls come with the court at no extra charge.\n"
                "Q: Is there a cancellation fee? A: No cancellation fee "
                "currently."
            )
        }
    ]

    rows = [
        {"category": item["category"], "content": chunk}
        for item in knowledge
        for chunk in chunk_text(item["text"])
    ]

    # Insert the new rows first and only then remove the old ones, so a failed
    # insert leaves the live knowledge base untouched rather than empty.
    try:
        inserted = supabase.table("knowledge_chunks").insert(rows).execute()
    except Exception as e:
        if "embedding" in str(e) and "null" in str(e).lower():
            raise SystemExit(
                "knowledge_chunks.embedding is still NOT NULL from the embedding era.\n"
                "Run this once in the Supabase SQL Editor, then seed again:\n"
                "  alter table public.knowledge_chunks alter column embedding drop not null;"
            )
        raise

    new_ids = [r["id"] for r in (inserted.data or [])]
    if replace and new_ids:
        # Guarded: an empty id list would make "not in ()" match every row.
        supabase.table("knowledge_chunks").delete().not_.in_("id", new_ids).execute()

    _cache["chunks"] = None  # next load_knowledge() call picks up the new rows
    print(f"[knowledge] Seeded {len(rows)} chunks from {len(knowledge)} knowledge items.")


def load_knowledge() -> list[str]:
    """Return every knowledge chunk, in a stable order. Never raises.

    On a failed read it serves the last good copy if there is one, and [] if
    not; the prompt then tells Ace not to quote prices or policies it cannot
    see. Raising would abort the whole reply and leave the customer with
    silence instead.
    """
    now = time.monotonic()
    if _cache["chunks"] is not None and now - _cache["loaded_at"] < _CACHE_TTL_SECONDS:
        return _cache["chunks"]
    try:
        result = (
            supabase.table("knowledge_chunks")
            .select("content")
            .order("id")
            .execute()
        )
        chunks = [r["content"] for r in (result.data or []) if (r.get("content") or "").strip()]
        _cache.update(chunks=chunks, loaded_at=now)
        return chunks
    except Exception as e:
        print(f"[knowledge] load failed ({type(e).__name__}: {e}) - using {'cached copy' if _cache['chunks'] else 'no context'}")
        return _cache["chunks"] or []


if __name__ == "__main__":
    seed_knowledge()
