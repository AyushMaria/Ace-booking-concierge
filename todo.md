# 🎾 Ace — Improvement To-Do List

## 🎾 Customer-Facing (Ace)

- [x] **Booking Reminders** — Add Railway Cron job to query upcoming bookings 1–2 hours before slot start time and fire a Twilio outbound WhatsApp message (e.g. "Hey Ayesha! Your court is in 1 hour 🎾")

- [ ] **Cancellation Window Enforcement** — Block cancellations within 30 minutes of slot start time in `cancel_booking`; surface a friendly message instead of silently succeeding

- [x] **Email Confirmation** — Handled via EmailJS on the website side ✅

- [ ] **Past Booking History** — Add `get_my_past_bookings(phone, limit)` tool; current `get_my_bookings` only fetches `.gte("booking_date", today)` so customers can't see their history

- [ ] **Waitlist for Fully-Booked Slots** — Add `join_waitlist(phone, date, slot)` tool writing to a `waitlists` Supabase table; auto-notify customer via WhatsApp when a cancellation frees their slot

- [ ] **Weekly Recurring Bookings** — Add `create_recurring_booking(phone, day_of_week, slots, weeks)` tool to auto-generate bookings for regular players without manual rebooking each week

- [ ] **Hindi / Marathi Language Support** — Add language detection step to Ace system prompt in `agent.py`; instruct Gemini to reply in the customer's detected language (no separate model needed)

---

## 🛠️ Admin-Facing (Ace Admin)

- [ ] **Daily Auto-Summary Report** — Add Railway Cron job at 11:55 PM IST to call `get_booking_stats()` and `get_revenue()` and push a daily summary to admin WhatsApp (e.g. "Today: 8 bookings | ₹2,000 revenue | 2 cancellations")

- [ ] **Multiple Admin Phones** — Change `ADMIN_PHONE` env var to comma-separated list; split into a set in `main.py` to support multiple staff with admin access without redeploying

- [ ] **Unblock Slots Tool** — Add `unblock_slots(date, slots)` tool in `tools.py` that deletes rows from `bookings` where `name = "BLOCKED"`; currently `block_slots` exists but has no reverse operation

- [ ] **Payment Status Tracking** — Add `paid` boolean column to `bookings` table in Supabase; add `mark_paid(booking_id)` admin tool so admin can ask "which bookings are unpaid today?"

- [ ] **Promo Code Usage Stats** — Add `get_promo_stats(code)` tool to surface usage count and total discount given per promo code; requires `uses_count` column or `promo_usage` join table in Supabase

- [ ] **CSV / Export Tool** — Add `export_bookings(after_date, before_date)` tool that generates a CSV and sends it as a WhatsApp document attachment via Twilio media API

---

## ⚙️ Infrastructure & Code

- [ ] **Persistent Sessions** — Replace in-memory dict in `sessions.py` with a `sessions` Supabase table (keyed by `phone`, storing JSON history array); fall back to empty history on missing row. Survives Railway restarts

- [ ] **Cache Agent at Module Level** — Move `create_react_agent(...)` out of `run_agent` / `run_admin_agent` in `agent.py`; cache at module level and inject time context as a user message instead of rebuilding the graph on every message

- [ ] **Twilio Signature Validation** — Add `twilio.request_validator.RequestValidator` middleware to `main.py`; prevents webhook spoofing by verifying every incoming POST is genuinely from Twilio

- [ ] **Rate Limiting** — Add per-phone cooldown (e.g. 1 request per 2 seconds) in `main.py` using an in-memory dict or Redis counter to prevent Gemini API flooding

- [ ] **Phone Normalization at Entry Point** — Call `normalize_phone()` once at the top of the webhook handler in `main.py` on the `From:` field before it reaches the agent; remove scattered per-tool normalization

- [ ] **Structured Logging** — Replace all `print()` calls across `main.py`, `agent.py`, `tools.py`, and `sessions.py` with Python `logging` module at `INFO`/`ERROR` levels for Railway log filtering

- [ ] **Expand Tool Docstrings** — Rewrite short/generic docstrings on `sync_website_customers`, `edit_booking_total`, `add_paddle_rental`, and other ambiguous tools with concrete when-to-call and when-NOT-to-call examples to reduce LLM hallucinated tool calls