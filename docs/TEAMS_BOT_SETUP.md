# Microsoft Teams Bot Setup — Gilbertus Albans

## Overview

Gilbertus Albans exposes a Teams webhook at `POST /teams/webhook` that receives
Bot Framework messages and responds using the **business-only** content filter
(identical to `/presentation/ask`). No personal data (WhatsApp, ChatGPT) is
ever exposed through the Teams channel.

---

## 1. Azure Bot Registration

### 1.1 Create an Azure Bot resource

1. Go to [Azure Portal](https://portal.azure.com) > **Create a resource** > search for **Azure Bot**.
2. Fill in:
   - **Bot handle**: `gilbertus-albans`
   - **Subscription / Resource group**: your REH subscription
   - **Pricing tier**: F0 (free) is fine for initial testing
   - **Microsoft App ID**: choose **Create new Microsoft App ID**
3. Click **Create**.

### 1.2 Obtain credentials

1. After creation, go to the Bot resource > **Configuration**.
2. Copy the **Microsoft App ID** — this is `TEAMS_APP_ID`.
3. Click **Manage password** next to the App ID.
4. Generate a new **Client Secret** — this is `TEAMS_APP_SECRET`.
5. Note your **Tenant ID** from Azure AD — this is `TEAMS_TENANT_ID`.

### 1.3 Set environment variables

Add to your `.env` file on the server:

```bash
TEAMS_APP_ID=<your-microsoft-app-id>
TEAMS_APP_SECRET=<your-client-secret>
TEAMS_TENANT_ID=<your-azure-ad-tenant-id>
```

---

## 2. Required Permissions

### Azure AD App Registration permissions

The bot's App Registration needs these **Application** permissions:

| Permission | Type | Purpose |
|---|---|---|
| `TeamsActivity.Send` | Application | Send proactive messages |

No additional Graph API permissions are needed — the bot only responds to
incoming messages via the Bot Framework REST API.

### Network / firewall

- The server must be reachable from Microsoft's Bot Framework service IPs on
  the configured port (HTTPS, port 443).
- Outbound HTTPS to `login.microsoftonline.com` and `*.botframework.com`.

---

## 3. Configure the Webhook URL

### 3.1 Set the messaging endpoint

1. In Azure Portal, go to your Bot resource > **Configuration**.
2. Set **Messaging endpoint** to:

```
https://<your-server-domain>/teams/webhook
```

For example:
```
https://gilbertus.respectenergy.pl/teams/webhook
```

### 3.2 HTTPS requirement

Microsoft requires HTTPS with a valid TLS certificate. Options:

- **Production**: Use your existing nginx/Caddy reverse proxy with Let's Encrypt.
- **Development**: Use [ngrok](https://ngrok.com) to tunnel:

```bash
ngrok http 8000
# Then set the messaging endpoint to: https://<ngrok-id>.ngrok.io/teams/webhook
```

### 3.3 Add the Teams channel

1. In Azure Portal > Bot resource > **Channels**.
2. Click **Microsoft Teams** to enable the Teams channel.
3. Accept the terms and save.

---

## 4. Install the Bot in Teams

### Option A: Sideload for testing

1. Create an `app-manifest.zip` containing:
   - `manifest.json` (see template below)
   - Two icon files: `color.png` (192x192) and `outline.png` (32x32)
2. In Teams, go to **Apps** > **Manage your apps** > **Upload a custom app**.
3. Select the zip and install.

#### manifest.json template

```json
{
  "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.17/MicrosoftTeams.schema.json",
  "manifestVersion": "1.17",
  "version": "1.0.0",
  "id": "<TEAMS_APP_ID>",
  "developer": {
    "name": "Respect Energy",
    "websiteUrl": "https://respectenergy.pl",
    "privacyUrl": "https://respectenergy.pl/privacy",
    "termsOfUseUrl": "https://respectenergy.pl/terms"
  },
  "name": {
    "short": "Gilbertus Albans",
    "full": "Gilbertus Albans — Business Intelligence Assistant"
  },
  "description": {
    "short": "Asystent biznesowy Respect Energy",
    "full": "Gilbertus Albans to asystent biznesowy z dostepem do pelnej komunikacji firmowej. Odpowiada wylacznie na pytania biznesowe."
  },
  "icons": {
    "color": "color.png",
    "outline": "outline.png"
  },
  "accentColor": "#1E3A5F",
  "bots": [
    {
      "botId": "<TEAMS_APP_ID>",
      "scopes": ["personal", "team", "groupChat"],
      "commandLists": [
        {
          "scopes": ["personal", "team", "groupChat"],
          "commands": [
            {
              "title": "pomoc",
              "description": "Wyswietl informacje o dostepnych funkcjach"
            },
            {
              "title": "brief",
              "description": "Poranny brief — podsumowanie ostatnich wydarzen"
            }
          ]
        }
      ]
    }
  ],
  "permissions": ["identity", "messageTeamMembers"],
  "validDomains": []
}
```

### Option B: Publish to org app catalog

1. In Teams Admin Center, go to **Manage apps** > **Upload new app**.
2. Upload the same `app-manifest.zip`.
3. Users can then install from the org catalog.

---

## 5. Testing

### 5.1 Verify the webhook is reachable

```bash
curl -X POST https://<your-server>/teams/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message",
    "text": "Jakie sa najnowsze kontrakty tradingowe?",
    "from": {"id": "test-user", "name": "Test"},
    "conversation": {"id": "test-conv"},
    "serviceUrl": "https://smba.trafficmanager.net/emea/",
    "id": "test-activity-1"
  }'
```

Expected response:
```json
{"status": "ok", "message": "reply sent"}
```

(The actual reply will be sent via Bot Framework to the conversation, so it
will fail on `serviceUrl` in a raw curl test — but the 200 confirms the
endpoint works.)

### 5.2 Test in Teams

1. Open Teams and find the bot in your installed apps.
2. Start a personal chat and send a message like:
   - `Kto odpowiada za magazyny energii?`
   - `Jakie spotkania odbyly sie w tym tygodniu?`
3. Verify:
   - The bot responds with business-relevant content.
   - No personal data (WhatsApp messages, ChatGPT conversations) appears.

### 5.3 Test @mention in a channel

1. Add the bot to a Teams channel.
2. Send `@Gilbertus Albans jaki jest status projektu PV Chmielnik?`
3. The bot should strip the mention and answer the business query.

### 5.4 Check logs

```bash
# On the server, watch the API logs:
tail -f /home/sebastian/personal-ai/logs/api.log | grep -i teams
```

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot does not respond | Messaging endpoint wrong or unreachable | Check Azure Bot > Configuration > Messaging endpoint |
| 502 on reply | Token request failed | Verify `TEAMS_APP_ID`, `TEAMS_APP_SECRET`, `TEAMS_TENANT_ID` in `.env` |
| Bot replies but content is empty | No matching business chunks | Check Qdrant is running and has indexed data |
| Personal data in responses | Blocked source types leaking | Check logs for `Presentation filter: blocked leaked match` warnings |

---

## 7. Architecture

```
Teams Client
    |
    v
Microsoft Bot Framework Service
    |
    v  (POST /teams/webhook)
FastAPI  (teams_bot.py)
    |
    +--> _strip_mention()       — clean @mention tags
    +--> _business_ask()        — RAG pipeline with BUSINESS-ONLY filter
    |       |
    |       +--> interpret_query()
    |       +--> search_chunks()        [source_types = ALLOWED only]
    |       +--> _validate_no_blocked() [defence-in-depth]
    |       +--> cleanup_matches()
    |       +--> redact_matches()
    |       +--> answer_question()      [TEAMS_SYSTEM_ADDENDUM]
    |
    +--> _send_reply()          — Bot Framework REST API
            |
            v
    Teams Client (response appears in chat)
```
