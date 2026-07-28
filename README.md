# Ace — WhatsApp Booking Concierge

> An AI-powered WhatsApp booking agent for Vibe & Volley Pickleball Courts, built with LangGraph, Google Gemini, FastAPI, and Supabase.

## Overview

Ace is a conversational WhatsApp bot that automates court bookings, cancellations, and customer support for a pickleball venue. It operates in two modes:

- **Customer Mode** — Check slot availability, create/cancel/edit bookings, view upcoming reservations, and get answers to FAQs via retrieval-augmented generation (RAG).
- **Admin Mode** — Full operational control: view/search/delete/edit any booking, manage promo codes, block slots for maintenance, and pull revenue reports.

The agent runs on **Gemini 2.5 Flash** via LangChain/LangGraph's `create_react_agent`, is exposed as a **FastAPI** webhook, and integrates with the **Twilio WhatsApp Business API** for messaging. It is deployed on **Railway**.

## Features

### Customer-Facing
- Real-time slot availability checks (7 AM–11 PM daily)
- Booking creation with automatic phone/name resolution from prior bookings
- Booking cancellation and editing (date, slots, or both)
- View upcoming personal bookings
- Promo code application (customer-provided codes only)
- Paddle rental upsell (₹50/paddle/hour)
- Payment mode selection (Cash or UPI, post-play)
- RAG-backed answers to FAQs (pricing, court rules, location, timings)
- Automated WhatsApp booking reminders via a scheduled cron job

### Admin-Only
- View all bookings for any date or date range
- Search bookings by phone number or customer name
- Delete bookings by ID
- Block slots for maintenance or private events
- Revenue reports with filters (date range, customer)
- Create and edit promo codes
- Edit booking details (date, slots) or override totals
- Sync customer profiles from the venue's website

## Reliability Fixes (Date & Session Handling)

Ace has been hardened against date hallucination — a failure mode where the LLM computes "today" incorrectly across long-running or multi-day WhatsApp conversations. Key safeguards now in place:

- **Deterministic date resolution** — `resolve_date()` in `tools.py` parses natural phrases ("today", "tomorrow", "next friday", DD Mon YYYY) into strict ISO dates server-side, rather than relying on the LLM's own date arithmetic.
- **Session rollover deduplication** — `sessions.py` strips any stale "date has changed" system notes before injecting a fresh one, preventing conflicting anchors from stacking up in long conversations.
- **History capping** — conversation history per user is capped to a fixed number of recent messages to reduce stale-context bleed and token overhead.
- **Dynamic prompt examples** — example dates shown to the LLM in prompts and tool docstrings are computed relative to the current date rather than hardcoded, preventing year/date drift.
- **Diagnostic logging** — key checkpoints (`get_session`, `get_system_prompt`, `check_available_slots`) log the raw and resolved date values for traceability in production logs (Railway).

## Tech Stack

| Layer | Technology |
|---|---|
| AI Agent | LangGraph + LangChain |
| LLM | Google Gemini 2.5 Flash (`langchain-google-genai`) |
| Backend | FastAPI + Uvicorn |
| Messaging | Twilio WhatsApp Business API |
| Database | Supabase (PostgreSQL + `pgvector`) |
| Knowledge Retrieval | RAG over `pgvector`-embedded FAQ/policy chunks (`rag.py`) |
| Session State | Persisted per-phone-number history (Supabase-backed) |
| Reminders | Scheduled cron endpoint for booking reminders (`reminders.py`, `reminder_script.py`) |
| Deployment | Railway (`Procfile` + `runtime.txt`) |
| Timezone | IST (Asia/Kolkata), via `pytz` |

## Project Structure

```
Ace-booking-concierge/
├── main.py              # FastAPI app, Twilio webhook, cron endpoints, phone normalization at entry
├── agent.py             # LangGraph agent setup, system prompts (customer + admin), run functions
├── tools.py             # LangChain tools: booking CRUD, slot checks, promo codes, date resolution
├── rag.py               # RAG knowledge base: FAQ/policy chunks, embedding + retrieval logic
├── sessions.py          # Per-user session/history management, date-rollover handling
├── reminders.py         # WhatsApp booking reminder logic (approved template messages)
├── reminder_script.py   # Standalone/cron-triggered reminder dispatch script
├── requirements.txt     # Python dependencies
├── Procfile             # Railway process definition
├── runtime.txt          # Python version pin for Railway
└── .env_template        # Required environment variable names (copy to .env)
```

## Getting Started

### Prerequisites

- Python 3.11+
- A [Twilio](https://www.twilio.com/) account with WhatsApp enabled
- A [Supabase](https://supabase.com/) project with booking, session, and `pgvector`-enabled knowledge tables
- A [Google AI](https://aistudio.google.com/) API key (Gemini)

### 1. Clone the Repository

```bash
git clone https://github.com/AyushMaria/Ace-booking-concierge.git
cd Ace-booking-concierge
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env_template` to `.env` and fill in the required values:

```
GOOGLE_API_KEY=your_google_gemini_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_role_key
TWILIO_AUTH_TOKEN=your_twilio_auth_token
ADMIN_PHONE=whatsapp:+91XXXXXXXXXX
```

### 4. Run Locally

```bash
uvicorn main:app --reload
```

Expose your local server with [ngrok](https://ngrok.com/) and set the resulting URL as the webhook in your Twilio console:

```
https://<your-ngrok-domain>/webhook
```

## Deployment (Railway)

This project is pre-configured for Railway:

1. Push changes to GitHub (`main` branch).
2. Create a Railway project and connect this repository.
3. Add all required environment variables in the Railway dashboard.
4. Railway uses `Procfile` and `runtime.txt` to start the server automatically on every push.
5. Configure a Railway cron trigger (or external scheduler) to hit the reminders endpoint for booking notifications.

## How the Agent Works

1. A WhatsApp message arrives at the `/webhook` endpoint via Twilio.
2. `main.py` normalizes the sender's phone number at the entry point before any downstream processing.
3. `sessions.py` retrieves the conversation history for that phone number, deduplicating and injecting a date-rollover note if the session is stale.
4. If the sender matches `ADMIN_PHONE`, the **admin agent** is invoked; otherwise the **customer agent** runs.
5. `rag.py` retrieves relevant knowledge chunks (FAQs, policies) to supplement the system prompt for that turn.
6. The LangGraph `create_react_agent` reasons over the conversation and calls tools from `tools.py` as needed (slot checks, booking CRUD, promo codes).
7. The response is sent back to the user via Twilio's WhatsApp reply.
8. A separate scheduled job (`reminders.py` / `reminder_script.py`) sends approved WhatsApp template reminders for upcoming bookings.

## Court Info

| Detail | Info |
|---|---|
| Venue | Vibe & Volley Pickleball Courts |
| Location | By Tiny Tots Kindergarten, Chh. Sambhajinagar |
| Timings | Mon–Sun, 7–11 AM & 4–11 PM |
| Slot Price | ₹250 / 30 min (₹500/hr) |
| Paddle Rental | ₹50 / paddle / hour |
| Payment | Cash or UPI (post-play) |
| Contact | +91 9156156570 |

## License

This project is private. All rights reserved © Ayush Maria.
