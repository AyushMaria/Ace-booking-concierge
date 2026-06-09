import os
import re
from supabase import create_client
from google.genai import Client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

EMBED_MODEL = "gemini-embedding-2"

def get_embedding(text: str) -> list[float]:
    client = Client(api_key=os.getenv("GEMINI_API_KEY"))
    result = client.models.embed_content(model=EMBED_MODEL, contents=text)
    return result.embeddings[0].values


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


def seed_knowledge():
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
                "Premium paddle rental: ₹50/paddle/hour. Max 2 paddles per "
                "booking.\n"
                "Available paddle models: Perseus IV, Agassi, j2nf, Boomstick.\n"
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
                "RULE 5 — Time between 11 AM and 4 PM: court is closed, offer "
                "nearest slot or call +919156156570.\n"
                "RULE 6 — '11' for today in evening → assume 11 PM. Never book "
                "past 12:00 AM. Never suggest a slot that already started."
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
                "- VIBESLOT: active for selected customers only, valid for "
                "bookings of at least 1 hour."
            )
        },
        {
            "category": "booking_flow",
            "text": (
                "BOOKING FLOW:\n"
                "1. Silently call get_customer_by_phone before responding.\n"
                "2. Returning customer: greet by name, ask only for payment "
                "mode. Use saved email — never guess.\n"
                "3. New customer: ask Name | Email | Payment mode.\n"
                "4. After create_booking succeeds: NEVER re-check availability. "
                "Treat as confirmed.\n"
                "5. After success, send two-part reply separated by [SPLIT]: "
                "confirmation + paddle upsell.\n"
                "6. If customer replies 'Ok', 'Fine', 'Sure', 'Alright' — "
                "treat as acceptance, do not re-ask.\n"
                "7. Payment must be Cash or UPI. If invalid, ask only for "
                "payment mode.\n"
                "8. Customer phone is from session — never ask for it, never "
                "display it unless explicitly asked."
            )
        },
        {
            "category": "paddles",
            "text": (
                "PADDLE RENTAL:\n"
                "- Premium paddles: ₹50/paddle/hour.\n"
                "- Max 2 paddles per booking. 4 total available across all "
                "bookings.\n"
                "- Models: Perseus IV, Agassi, j2nf, Boomstick.\n"
                "- After booking confirmation, mention paddles in a [SPLIT] "
                "message.\n"
                "- Do NOT wait for a reply to the paddle message.\n"
                "- If customer asks to add paddles, call add_paddle_rental.\n"
                "- Never follow up asking if they want paddles again."
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
                "Q: Do you provide free paddles? A: Yes, we provide both free and paid paddles as per customer requirement.\n"
                "Q: Is there a cancellation fee? A: No cancellation fee "
                "currently."
            )
        }
    ]

    for item in knowledge:
        chunks = chunk_text(item["text"])
        for chunk in chunks:
            embedding = get_embedding(chunk)
            supabase.table("knowledge_chunks").insert({
                "category": item["category"],
                "content": chunk,
                "embedding": embedding
            }).execute()

    print(f"[RAG] Seeded {len(knowledge)} knowledge items.")


def retrieve_knowledge(query: str, top_k: int = 5, category: str = None) -> list[str]:
    query_embedding = get_embedding(query)
    params = {"query_embedding": query_embedding, "match_count": top_k}
    if category:
        params["filter_category"] = category

    result = supabase.rpc("match_knowledge", params).execute()
    return [row["content"] for row in result.data]
