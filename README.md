# 🎾 Ace — WhatsApp Booking Concierge

> A WhatsApp-powered AI booking agent for **Vibe & Volley Pickleball Courts**, built with LangGraph, Google Gemini, FastAPI, and Supabase.

---

## 📖 Overview

**Ace** is an intelligent WhatsApp concierge bot that handles court bookings, cancellations, and customer queries through natural conversation. It supports two modes:

- **Customer Mode** — Helps users check availability, book slots, cancel, and view their upcoming bookings.
- **Admin Mode** — Gives the court owner full database access: view all bookings, manage promo codes, block slots, get revenue stats, and more.

The agent is powered by **Gemini 2.5 Flash** via LangChain and deployed as a **FastAPI** webhook, ready to integrate with the **Twilio WhatsApp Business API**.

---

## ✨ Features

### Customer-Facing
- 📅 Check available court slots in real-time
- 📝 Create bookings (collects name, phone, email, date, time)
- ❌ Cancel bookings
- 👀 View upcoming personal bookings
- 🏷️ Apply promo codes (customer-provided only)
- 🏓 Paddle rental upsell (₹50/paddle/hour)
- 💳 Payment mode selection (Cash or UPI)

### Admin-Only
- 📊 View all bookings for any date
- 🗑️ Delete bookings by ID
- 🚫 Block slots (maintenance, private events)
- 💰 Revenue reports with filters (date range, customer name/phone/email)
- 🔍 Search bookings by phone or name
- 🎟️ Create & edit promo codes
- ✏️ Edit booking details or override totals

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| AI Agent | LangGraph + LangChain |
| LLM | Google Gemini 2.5 Flash |
| Backend | FastAPI + Uvicorn |
| WhatsApp | Twilio API |
| Database | Supabase (PostgreSQL) |
| Session State | In-memory (per phone number) |
| Deployment | Railway (Procfile + runtime.txt) |
| Timezone | IST (Asia/Kolkata) |

---

## 📁 Project Structure

```
whatsapp-agent/
├── main.py           # FastAPI app & Twilio webhook handler
├── agent.py          # LangGraph agent setup, system prompts, run functions
├── tools.py          # All LangChain tools (booking, slots, promo, admin)
├── sessions.py       # Per-user session/history management
├── requirements.txt  # Python dependencies
├── Procfile          # Railway deployment process
└── runtime.txt       # Python version for Railway
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- A [Twilio](https://www.twilio.com/) account with WhatsApp enabled
- A [Supabase](https://supabase.com/) project with booking tables set up
- A [Google AI](https://aistudio.google.com/) API key (Gemini)

### 1. Clone the Repository

```bash
git clone https://github.com/AyushMaria/whatsapp-agent.git
cd whatsapp-agent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
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

Expose your local server with [ngrok](https://ngrok.com/) and set the webhook URL in your Twilio console:

```
https://<your-ngrok-url>/webhook
```

---

## ☁️ Deployment (Railway)

This project is pre-configured for Railway deployment.

1. Push to GitHub
2. Create a new Railway project and connect this repo
3. Add all environment variables in the Railway dashboard
4. Railway will use the `Procfile` to start the server automatically

---

## 🤖 How the Agent Works

1. A WhatsApp message arrives at the `/webhook` endpoint via Twilio.
2. `sessions.py` retrieves the conversation history for the sender's phone number.
3. If the sender matches `ADMIN_PHONE`, the **admin agent** is invoked; otherwise the **customer agent** runs.
4. The LangGraph `create_react_agent` reasons over the conversation and calls the appropriate tools from `tools.py`.
5. The response is sent back to the user via Twilio's WhatsApp reply.

---

## 🏟️ Court Info

| Detail | Info |
|---|---|
| Venue | Vibe & Volley Pickleball Courts |
| Location | By Tiny Tots Kindergarten, Chh. Sambhajinagar |
| Timings | Mon–Sun, 7–11 AM & 4–11 PM |
| Slot Price | ₹250 / 30 min (₹500/hr) |
| Paddle Rental | ₹50 / paddle / hour |
| Payment | Cash or UPI (post-play) |
| Contact | +91 9156156570 |

---

## 📄 License

This project is private. All rights reserved © Ayush Maria.
