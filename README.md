# Boston DSA Discord Verification Bot

A Discord bot that verifies DSA membership status and automatically manages the **DSA Member** role on the Boston DSA Discord server. Membership is checked against our Action Network database. Verified members are re-checked weekly, and anyone whose membership has lapsed is moved to the **Lapsed Member** role and notified by DM.

---

## How it works

### Member verification flow

1. A member runs `/verify` in Discord and provides their DSA email address
2. The bot validates the email format, then sends a 6-digit verification code to that address
3. The member runs `/confirm` with the code (expires in 10 minutes)
4. The bot checks Action Network — if the `is_member` field is `"True"`, the **DSA Member** role is assigned
5. The Discord ID and email are stored in a local database for future sync checks

### Weekly membership sync

Every Saturday, the bot re-checks every verified member against Action Network. If a member's `is_member` field is no longer `"True"`:

- The **DSA Member** role is removed
- The **Lapsed Member** role is assigned
- The member receives a DM explaining the change and linking to https://dsausa.org/join to rejoin

If a lapsed member later rejoins DSA and re-runs `/verify`, the **DSA Member** role is restored and **Lapsed Member** is removed.

---

## Moderator commands

All mod commands are restricted to users with the **Moderator** role and return responses visible only to the mod who ran them.

| Command | Description |
|---------|-------------|
| `/lookup @member` | Shows the DSA email address linked to a Discord member, and whether their membership is currently active or lapsed |
| `/unlink @member` | Removes a member's verification record and roles, so they can re-verify (e.g. after a Discord account change). The member is notified by DM. |

---

## Rollout strategy

The server currently has existing members with the **DSA Member** role who predate this bot. To avoid mass role removal on the first sync, the recommended rollout is:

1. Rename the existing **DSA Member** role to **DSA Active Member** in Discord server settings
2. Create a new empty **DSA Member** role — this is what the bot will assign
3. Launch the bot and announce verification to members, giving them ample time to verify
4. Once adoption is sufficient, remove **DSA Active Member** from all remaining users and the old role can be deleted

This approach requires no code changes and is fully reversible at any point before the final switchover.

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

> **Important:** In your server's role list (Server Settings → Roles), drag the bot's role above both **DSA Member** and **Lapsed Member**. Discord will not allow a bot to assign or remove roles ranked higher than its own.

### 2. Get your Discord Server ID

Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode), then right-click your server name and click **Copy Server ID**. This is your `DISCORD_GUILD_ID`.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Fill in all values in `.env`:

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Bot token from the Discord Developer Portal |
| `DISCORD_GUILD_ID` | Your Discord server ID |
| `ACTION_NETWORK_API_KEY` | API key from the Action Network admin dashboard |
| `SMTP_HOST` | SMTP server hostname (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (typically `587` for TLS) |
| `SMTP_USER` | Email account used to send verification codes |
| `SMTP_PASSWORD` | Password or app password for the SMTP account |
| `EMAIL_FROM` | The "from" address on verification emails (e.g. `noreply@bostondsa.org`) |

For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) rather than your account password.

### 4. Install dependencies and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

---

## Deployment

The bot should run on a persistent server (the chapter has a Linode) using `systemd` to keep it running across restarts and crashes.

Example `systemd` service file (`/etc/systemd/system/dsa-bot.service`):

```ini
[Unit]
Description=Boston DSA Discord Verification Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/discord-verification-bot-v2
EnvironmentFile=/home/ubuntu/discord-verification-bot-v2/.env
ExecStart=/home/ubuntu/discord-verification-bot-v2/.venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dsa-bot
sudo systemctl start dsa-bot
sudo systemctl status dsa-bot  # confirm it's running
```

View logs:

```bash
journalctl -u dsa-bot -f
```

---

## Security

### Verification code security
- Codes are generated using Python's `secrets` module, which is cryptographically secure
- Codes expire after 10 minutes
- After 5 incorrect attempts, the pending verification is invalidated and the member must request a new code via `/verify`

### Email and identity protection
- The bot validates email format before accepting input — malformed strings are rejected before reaching the Action Network API or email sender
- Each email address can only be linked to one Discord account at a time, preventing membership sharing
- Email addresses are never written to logs — only Discord IDs appear in log output

### Database
- Member emails and Discord IDs are stored in a local SQLite file (`members.db`)
- This file should be restricted to the process user only: `chmod 600 members.db`
- The host server should use encrypted disk storage (standard on Linode with a small configuration step)
- Back up `members.db` regularly to an encrypted location — losing it means all members would need to re-verify

### Credentials
- All secrets (bot token, API key, SMTP password) are stored in `.env`, which is excluded from version control via `.gitignore`
- Never commit `.env` to the repository
- Use the minimum necessary permissions for each credential: a read-only Action Network API key is sufficient if available

### Mod access
- The `/lookup` and `/unlink` commands are restricted to the **Moderator** role and return ephemeral responses (visible only to the mod who ran them)

---

## Files

| File | Purpose |
|------|---------|
| `bot.py` | Bot entry point — slash commands, role logic, weekly sync task |
| `action_network.py` | Action Network API client — membership status checks |
| `database.py` | SQLite store for Discord ID → email mappings |
| `email_verification.py` | Generates and validates 6-digit verification codes |
| `sync.py` | Weekly sync — re-checks all members, updates roles, DMs lapsed members |
