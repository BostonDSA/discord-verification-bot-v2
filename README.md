# Boston DSA Discord Verification Bot

Verifies DSA membership via Action Network and assigns the **DSA Member** role in Discord. Runs a weekly sync to remove the role from anyone whose membership has lapsed.

---

## How it works

1. A member runs `/verify` and provides their DSA email address
2. The bot sends a 6-digit code to that email
3. The member runs `/confirm` with the code
4. The bot checks Action Network — if `is_member == "True"`, the role is assigned
5. Every 7 days, the bot re-checks all verified members and removes the role (with a DM) from anyone no longer active

---

## Setup

### 1. Create the Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and click **New Application**
2. Name it (e.g. "Boston DSA Verification Bot") and save
3. Go to **Bot** in the left sidebar
   - Click **Reset Token** and copy the token — this is your `DISCORD_TOKEN`
   - Under **Privileged Gateway Intents**, enable **Server Members Intent**
4. Go to **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: `Manage Roles`, `Send Messages`
   - Copy the generated URL and open it to invite the bot to your server

> **Important:** In your server, make sure the bot's role is positioned *above* the **DSA Member** role in Server Settings → Roles. Discord won't let a bot assign roles higher than its own.

### 2. Get your Discord Server ID

Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode), then right-click your server name and click **Copy Server ID**. This is your `DISCORD_GUILD_ID`.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Fill in all values in `.env`. For Gmail SMTP, use an [App Password](https://support.google.com/accounts/answer/185833) rather than your account password.

### 4. Install dependencies and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

---

## Files

| File | Purpose |
|------|---------|
| `bot.py` | Bot entry point — slash commands, weekly sync task |
| `action_network.py` | Action Network API membership check |
| `database.py` | SQLite store for Discord ID → email mappings |
| `email_verification.py` | Sends and validates 6-digit verification codes |
| `sync.py` | Weekly sync logic — checks all members, removes lapsed |

---

## Deployment

For production, run the bot on a persistent server (VPS, Fly.io, Railway, etc.) using a process manager like `systemd` or `supervisor` to keep it running and restart it on failure.
