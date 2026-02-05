# Agentic Honey-Pot API

This project exposes a REST API that detects scam intent, engages scammers with a human-like agent, extracts intelligence, and sends the final result to the GUVI evaluation callback.

**Endpoints**
- `GET /health` -> service status
- `POST /api/message` -> process a message event and return the agent reply

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:HONEY_POT_API_KEY = "your-secret-key"
python main.py
```

## Request Format

```json
{
  "sessionId": "wertyu-dfghj-ertyui",
  "message": {
    "sender": "scammer",
    "text": "Your bank account will be blocked today. Verify immediately.",
    "timestamp": 1770005528731
  },
  "conversationHistory": [],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
```

## Required Headers

- `x-api-key`: your API key (matches `HONEY_POT_API_KEY` or `API_KEY`)
- `Content-Type`: `application/json`

## Response Example

```json
{
  "status": "success",
  "reply": "Can you send the verification link again? It is not opening on my phone.",
  "scamDetected": true,
  "engagementComplete": false,
  "intelligence": {
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": ["account", "blocked", "verify"]
  },
  "totalMessagesExchanged": 2
}
```

## Callback Behavior

When scam intent is confirmed and engagement is complete, the service automatically sends the final result to:

```
POST https://hackathon.guvi.in/api/updateHoneyPotFinalResult
```

Override the callback URL with `HONEY_POT_CALLBACK_URL` if needed.

## Notes

- The agent never reveals scam detection and avoids illegal instructions.
- Intelligence extraction collects UPI IDs, phone numbers, links, and account-like patterns.
- Session state is stored in-memory by `sessionId`.
