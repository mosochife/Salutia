# Salutia

Salutia is a lightweight greeting and announcement platform built for **Nigerian schools and hotels** to send seasonal greetings and notices via **SMS** and **Email** with built-in consent tracking, Nigerian SMS length/encoding guardrails, and an auditable send log.

## Features

- **Multi-Tenant Accounts:** Organisations (`school` or `hotel`) with authenticated staff dashboards.
- **Consent-Aware Contacts & CSV Bulk Upload:**
  - Stores email and/or `+234` phone numbers with explicit consent timestamps and opt-out checks.
  - Bulk CSV uploader (`/contacts/upload`) automatically converts Nigerian local formats (`0803...`, `234803...`) to `+234803...` and skips duplicates safely.
- **Nigerian SMS Guardrails & Live Character Counter:**
  - Warns in real time when a message exceeds **160 GSM-7 characters** or contains **emojis/non-GSM characters** (which drop Nigerian carrier limits to **70 characters** and multiply SMS page billing).
- **Safe Batch Sending & Send Log:**
  - Previews eligible vs. skipped contacts per channel before sending.
  - Records every attempt (`sent`, `skipped`, `failed`) in `send_log` and prevents accidental duplicate sends to the same recipient.
- **Swappable Delivery Providers:**
  - Uses `ConsoleProvider` automatically in tests and local development when API keys are unset.
  - Supports **Brevo** (Email) and **Termii** (Nigerian DND-compliant SMS) via `.env`.

## Quick Start

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the test suite
python -m pytest -q

# 4. Start the local server
python run.py
```

Open `http://127.0.0` in your browser to create your school or hotel account.

## Going Live with Brevo & Termii (Optional)

Create a `.env` file in the project root (never commit `.env` to Git):

```env
SECRET_KEY=replace-with-a-random-secret
BREVO_API_KEY=your_brevo_v3_api_key
BREVO_SENDER_EMAIL=greetings@yourdomain.com
BREVO_SENDER_NAME=Salutia
TERMII_API_KEY=your_termii_api_key
TERMII_SENDER_ID=YourApprovedID
TERMII_CHANNEL=dnd
```

> **Nigerian SMS Note:** Register your Alphanumeric Sender ID on Termii early (approval typically takes 3–7 business days) and use the `dnd` channel so messages reach numbers on MTN/Airtel/Glo/9mobile Do-Not-Disturb lists.
