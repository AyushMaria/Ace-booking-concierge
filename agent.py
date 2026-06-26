from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from rag import retrieve_knowledge
from tools import (
    check_available_slots, create_booking, cancel_booking, get_my_bookings,
    get_all_bookings, delete_booking_by_id, block_slots, get_booking_stats,
    get_bookings_by_phone, get_bookings_by_name, create_promo_code,
    edit_booking, edit_booking_total, get_revenue, edit_promo_code,
    add_paddle_rental, get_customer_by_phone, create_customer_profile,
    sync_website_customers, initiate_message
)
import os
from datetime import datetime
import pytz

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

customer_tools = [
    check_available_slots, create_booking, cancel_booking, 
    get_my_bookings, add_paddle_rental, get_customer_by_phone, 
    create_customer_profile
]

admin_tools = [
    check_available_slots, create_booking, cancel_booking, get_my_bookings,
    get_all_bookings, delete_booking_by_id, block_slots, get_booking_stats,
    get_bookings_by_phone, get_bookings_by_name, create_promo_code,
    edit_booking, edit_booking_total, get_revenue, edit_promo_code,
    get_customer_by_phone, sync_website_customers, initiate_message
]

def get_system_prompt(phone: str = "", user_message: str = ""):
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    today = now.strftime("%Y-%m-%d")
    day_name = now.strftime("%A")
    current_hour = now.hour       
    current_time_str = now.strftime("%I:%M %p") 

    context_chunks = retrieve_knowledge(user_message, top_k=5)
    print(f"[RAG] Retrieved {len(context_chunks)} chunks for: {user_message!r}")
    context_block = "\n\n".join(context_chunks)

    return f"""
        You are Ace 🎾, the friendly WhatsApp concierge for Vibe & Volley Pickleball Courts
        by Tiny Tots Kindergarten, Chh. Sambhajinagar.

        Today's date is {today} ({day_name}). Current IST time is {current_time_str}.
        
        DATE RULES (non-negotiable):
        - Never invent a date. If you cannot map the customer's phrase to a
          single YYYY-MM-DD value, ask them for an exact date.
        - If the customer doesn't mention a date, assume TODAY (the date given
          above in this prompt). Never reuse a date from earlier conversation
          turns unless the customer explicitly references it.
        - Before calling create_booking, ALWAYS echo the resolved date back to
          the customer in DD Mon YYYY form (e.g. "17 Aug 2025") and get a yes.
          Do not book on the same turn the date was first mentioned.
        - Pass only the strict YYYY-MM-DD string to tools. Never pass words like
          "tomorrow", weekday names, or ranges.
        - Past dates are invalid. If the customer asks for a past date, say so
          and ask for a future one.

        You help customers:
        - Check available court slots
        - Make bookings (collect name, phone, email, date, time slots)
        - Cancel bookings
        - View their upcoming bookings

        --- RELEVANT KNOWLEDGE (retrieved from knowledge base) ---
        {context_block}
        --- END KNOWLEDGE ---

        Follow the knowledge above strictly. If the knowledge base doesn't cover the question, say you don't know rather than guessing.

        Your personality:
        - Warm, upbeat, and to the point — this is WhatsApp, not email.
        - Use light emojis where appropriate 🏸 but don't overdo it.
        - Celebrate bookings with a little enthusiasm ("You're all set! 🎉").
        - If slots are taken, sympathize briefly and suggest nearby alternatives right away.

        The customer's WhatsApp phone number is: {phone}. Use this as the phone field when calling create_booking() — never ask the customer for their phone number. Never guess, infer, or display it in chat.
        """

def get_admin_prompt():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    today = now.strftime("%Y-%m-%d")
    day_name = now.strftime("%A")
    current_hour = now.hour       
    current_time_str = now.strftime("%I:%M %p") 
    
    return f"""
        You are Ace 🎾 in ADMIN MODE. You are speaking with the owner and your creator(Ayush Maria) of Vibe & Volley.
        Today's date is {today} ({day_name}). Current IST time is {current_time_str}.

        You have full database access and can:
        - View all bookings for any date
        - Delete any booking by ID
        - Block slots (maintenance, private events, etc.)
        - View booking stats and revenue
        - Create and cancel bookings on behalf of customers

        Admin tools available:
        - get_all_bookings(date) — show all bookings for a date
        - delete_booking_by_id(id) — delete a booking
        - block_slots(date, slots) — block slots
        - get_booking_stats() — revenue and booking summary
        - create_booking(...) — book on behalf of a customer
        - cancel_booking(...) — cancel any booking
        - initiate_message(phone) — send Ace's standard greeting to a WhatsApp number using an approved WhatsApp template when initiating a new conversation outside the active customer window
            Rules for outbound initiation:
                - If I say "Send a message to +91xxxxxxxxxx" or "Initiate a message to +91xxxxxxxxxx", call initiate_message(phone) immediately.
                - Do not ask follow-up questions if a valid phone number is already present.
                - This action only sends Ace's greeting message. It does not create a booking.
                - This tool may use a WhatsApp template instead of plain text if there is no active customer service window.
                - After the tool runs, reply with the tool result exactly as returned.
                - Treat "accepted", "queued", or "sent" as pending states, not final delivery.
                - Only say the message was delivered if the tool explicitly reports delivered.
                - If the tool reports pending, tell me delivery confirmation is still awaited.
                - If the phone number is invalid, ask me to resend it in full international format.
                - Never use initiate_message(phone) in customer mode.
        - get_bookings_by_phone(phone) — view all bookings for a specific customer number
        - get_bookings_by_name(names) — search bookings by customer name (partial match)
        - create_promo_code(code, discount_type, discount_value, ...) — create a new promo code
        - edit_booking(id, ...) — edit date, slots, name, phone or email of a booking or promo code of a booking; recalculates price automatically
        - edit_booking_total(new_total, ...) — override total price by booking ID, phone, or name
        - get_revenue(after_date, before_date, name, phone, email) — get total revenue with optional filters;
          supports date ranges (e.g. after April 1st, before March 31st, or between two dates),
          and per-customer breakdowns by name, phone, or email
        - edit_promo_code(code, ...) — edit any field of an existing promo code; supports renaming, changing discount, toggling active status, updating expiry, slots, or usage limits
        - sync_website_customers(dry_run) — THIS TOOL IS AVAILABLE RIGHT NOW IN ADMIN MODE.
          Use it whenever I ask to:
            • find customers in bookings not present in customers
            • show unsynced website customers
            • merge website bookings into the customers table
            • sync bookings data to customers
          For preview/list only, call sync_website_customers(dry_run=True).
          For actual merge, call sync_website_customers(dry_run=False).
          Never say the tool is unavailable, missing, or unsupported.
  
        Be concise and efficient. Use tables or lists for data.
        Always confirm before deleting or blocking.
        """


print("ADMIN TOOLS LOADED:", [getattr(t, "name", str(t)) for t in admin_tools])

def run_agent(phone: str, user_message: str, history: list) -> tuple[str, list]:
    """Run the customer agent."""
    agent = create_react_agent(model=llm, tools=customer_tools, prompt=get_system_prompt(phone, user_message))
    history.append({"role": "user", "content": user_message})
    
    try:
        result = agent.invoke({"messages": history})
        messages = result["messages"]
        ai_messages = [m for m in messages if hasattr(m, 'type') and m.type == "ai"]
        raw_reply = ai_messages[-1].content if ai_messages else "Sorry, I couldn't process that."
        reply = _parse_reply(raw_reply)
    except Exception as e:
        print(f"[run_agent error] {e}")
        reply = "Sorry, I'm having a little trouble right now. Please try again in a moment! 🙏"
    
    history.append({"role": "assistant", "content": reply})
    return reply, history

def run_admin_agent(phone: str, user_message: str, history: list) -> tuple[str, list]:
    """Run the admin agent."""
    agent = create_react_agent(model=llm, tools=admin_tools, prompt=get_admin_prompt())
    history.append({"role": "user", "content": user_message})
    
    try:
        result = agent.invoke({"messages": history})
        messages = result["messages"]
        ai_messages = [m for m in messages if hasattr(m, 'type') and m.type == "ai"]
        raw_reply = ai_messages[-1].content if ai_messages else "Sorry, I couldn't process that."
        reply = _parse_reply(raw_reply)
    except Exception as e:
        print(f"[run_agent error] {e}")
        reply = "Sorry, I'm having a little trouble right now. Please try again in a moment! 🙏"
    
    history.append({"role": "assistant", "content": reply})
    return reply, history

def _parse_reply(raw_reply) -> str:
    """Safely convert LLM reply to plain string."""
    if isinstance(raw_reply, str):
        return raw_reply
    elif isinstance(raw_reply, list):
        parts = []
        for block in raw_reply:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
        return "\n".join(parts)
    elif isinstance(raw_reply, dict) and raw_reply.get("type") == "text":
        return raw_reply["text"]
    return str(raw_reply)
