#CraneBot

> Self-contained Discord bot for communities — onboarding, tickets, moderation, meetings, standups, and a live GitHub activity feed.

> "Caveman architecture." One file. No cogs. No ORM. Read `bot.py` top to bottom and understand everything.
---
## Features

| Feature | Description |
|---|---|
| **Welcome & Role Reactions** | Auto-welcome message + emoji-based self-serve roles (Founder / Engineer / Designer / Marketing) |
| **Private Tickets** | `!ticket <topic>` opens a private channel, `!close` shuts it down |
| **Moderation** | Kick, ban, bulk purge, full mod-log channel |
| **PIN-gated Admin Mode** | `!admin <pin>` unlocks meeting-schedule and ban commands (auto-expires) |
| **Meetings** | Schedule announcements + post join links |
| **Daily Standup** | Auto-ping every 24h with a reminder prompt |
| **In-channel Reminders** | `!remind <minutes> <text>` for quick pings |
| **GitHub Webhook Feed** | Push commits, PRs, and issues straight into `#github-feed` |
| **Server Setup Script** | One-shot `setup_channels.py` builds the full category/channel structure |
---
##Prerequisites

- **Python 3.10+**
- A [Discord Application & Bot Token](https://discord.com/developers/applications)
  - Enable **Server Members Intent** and **Message Content Intent** under the "Bot" settings tab
- Invite the bot to your server with at minimum these permissions:
  - Manage Roles, Manage Channels, Kick Members, Ban Members, Manage Messages, Send Messages, Read Message History, Add Reactions
---
##Quick Start (Local)

```bash
# 1. Clone and install
git clone <your-repo-url>
cd CraneBot
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — see the Configuration section below

# 3. (First time only) Build server channels & roles
python3 setup_channels.py
# Copy the IDs it prints into your .env file

# 4. Run the bot
python3 bot.py
```

---

## Configuration

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required? | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | **Yes** | — | Your Discord bot token |
| `GUILD_ID` | Setup only | — | Your server ID (enable Dev Mode in Discord → right-click server → Copy ID) |
| `WELCOME_CHANNEL_ID` | **Yes** | — | `#welcome-rules` channel ID |
| `GITHUB_FEED_CHANNEL_ID` | **Yes** | — | `#github-feed` channel ID |
| `MOD_LOG_CHANNEL_ID` | **Yes** | — | Channel for kick/ban audit logs |
| `STANDUP_CHANNEL_ID` | **Yes** | — | Daily standup ping channel |
| `MEETINGS_CHANNEL_ID` | **Yes** | — | Meeting announcements + links channel |
| `TICKET_CATEGORY_ID` | **Yes** | — | The `TICKETS` category ID (created by `setup_channels.py`) |
| `ROLE_SELECT_MESSAGE_ID` | **Yes** | — | Pin a message in `#welcome-rules`, copy its ID here |
| `GITHUB_WEBHOOK_SECRET` | Optional | — | Shared secret to verify GitHub webhook signatures |
| `WEBHOOK_PORT` | No | `8080` | Port for the GitHub webhook listener |
| `ADMIN_PIN` | Optional | — | PIN code that unlocks `!schedule`, `!meetlink`, `!ban` |
| `ADMIN_SESSION_MINUTES` | No | `15` | How long an `!admin` session lasts before re-locking |

>**Never commit `.env`.** It's already in `.gitignore`.

---

##Setting Up the Server Structure

Run `setup_channels.py` **once** against your empty guild. It will:

1. Create the 4 default roles: `Founder`, `Engineer`, `Designer`, `Marketing`
2. Build the full category + text-channel layout:
   - **INFO / ONBOARDING** — welcome-rules, announcements, roadmap-milestones
   - **GENERAL** — general, random
   - **TEAM-WISE** — product-strategy, engineering-ai-ml, fullstack-dev, arvr-flutter, iot-hardware, cloud-infra-security, ui-ux-design, marketing-growth, ops-admin
   - **BUSINESS** — pilot-partners, investor-incubation, customer-feedback
   - **DEV-OPS** — bug-tracker, deployments, github-feed
3. Create a `TICKETS` category (used by `!ticket`)

After it runs, copy-paste the printed IDs into `.env`. For the `ROLE_SELECT_MESSAGE_ID`:

1. Go to `#welcome-rules` and send a message like:
   ```
   React to grab your role:
   Founder  ·   Engineer  ·   Designer  ·   Marketing
   ```
2. Pin it, right-click → Copy Message ID → paste into `.env`.

---

##Command Reference

### Everyone

| Command | Description |
|---|---|
| `!help` | Show all commands in an embed |
| `!ticket <topic>` | Open a private ticket channel under the TICKETS category |
| `!close` | Close & delete the current ticket channel (Manage Channels perm required) |
| `!remind <minutes> <text>` | Ping yourself with a reminder in the same channel (Manage Guild perm) |

### Moderator (perms-based)

| Command | Required Perm | Description |
|---|---|---|
| `!kick <@member> [reason]` | Kick Members | Kick a member + log it |
| `!purge <amount>` | Manage Messages | Bulk-delete messages in-channel |

### Admin (PIN-gated via `!admin <pin>`)

| Command | Description |
|---|---|
| `!admin <pin>` | Unlock the admin-only commands (send via DM to avoid leaking) |
| `!lock` | Lock admin mode early |
| `!schedule <YYYY-MM-DD> <HH:MM> [topic]` | Post a meeting announcement to the meetings channel |
| `!meetlink <url> [label]` | Post a join link to the meetings channel |
| `!ban <@member> [reason]` | Ban a member (also needs Ban Members server perm) |

### Automatic

- **Welcome message** — Posts on `on_member_join` in `#welcome-rules`
- **Role reactions** — React/unreact on the pinned welcome message to add/remove roles
- **Daily standup** — Pings the standup channel every 24 hours
- **GitHub feed** — Listens on `POST http://<your-host>:8080/github` and relays pushes, PRs, and issues

---

##GitHub Webhook Setup

The bot ships with a built-in aiohttp web server sharing the bot's event loop.

1. Choose a machine with a public IP / domain (or use something like [ngrok](https://ngrok.com/) for testing).
2. In your GitHub repo → **Settings → Webhooks → Add webhook**:
   - Payload URL: `http://<your-server>:8080/github`
   - Content type: `application/json`
   - Secret: match your `GITHUB_WEBHOOK_SECRET` value (recommended)
   - Events: select **Just the push event**, **Pull requests**, and **Issues**
3. On the server, make sure port `8080` (or your `WEBHOOK_PORT`) is open.

---

##Production Deployment (systemd on Ubuntu)

The repo includes `cranebot.service` (and `trackforge-bot.service` as a legacy alias). Adjust the paths and user to match your server:

```ini
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/cranebot
ExecStart=/home/ubuntu/cranebot/venv/bin/python3 bot.py
EnvironmentFile=/home/ubuntu/cranebot/.env
```

Install:

```bash
# 1. On the server
git clone <your-repo> /home/ubuntu/cranebot
cd /home/ubuntu/cranebot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Drop in your .env (DO NOT commit this)
# Use scp or a secrets manager; never paste tokens into GitHub

# 3. Install the service
sudo cp cranebot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cranebot

# 4. Check status / logs
sudo systemctl status cranebot
sudo journalctl -u cranebot -f
```

---

##Project Layout

```
CraneBot/
├── .env.example          # Template for required env vars
├── .gitignore            # Ignores .env, venv, pycache, IDE files, etc.
├── bot.py                # The entire bot (commands, events, webhook server)
├── setup_channels.py     # One-shot server-structure builder
├── requirements.txt      # Python dependencies
├── cranebot.service      # systemd unit for production (primary)
└── trackforge-bot.service  # systemd unit — legacy alias
```

---

##Security Notes

- **`.env` must never be committed.** It contains secrets. `.env.example` is safe.
- Use `!admin <pin>` via DM — the bot auto-deletes public pin messages when possible.
- The GitHub webhook verifies `X-Hub-Signature-256` HMAC signatures when `GITHUB_WEBHOOK_SECRET` is set. **Always set it in production.**
- Give the bot only the Discord permissions it actually needs.

---

##Troubleshooting

| Symptom | Fix |
|---|---|
| `KeyError: DISCORD_TOKEN` | You didn't create `.env` or `load_dotenv()` failed. |
| Role reactions do nothing | `ROLE_SELECT_MESSAGE_ID` is wrong, or the bot lacks `Manage Roles` (and its role must be *above* the roles it assigns). |
| Ticket channel not created | `TICKET_CATEGORY_ID` is wrong or the bot lacks `Manage Channels`. |
| `401 bad signature` on GitHub webhook | `GITHUB_WEBHOOK_SECRET` on the server doesn't match the GitHub webhook secret. |
| `discord.HTTPException` on username rename | Rate-limited (max 2 per hour). Harmless — comment out the rename block if it's noisy. |
| Standup not firing daily | Bot restarted? The loop resets. It will fire 24h after the last restart. |

---

##Tech Stack

- **[discord.py 2.x](https://github.com/Rapptz/discord.py)** — Discord API wrapper
- **[aiohttp](https://github.com/aio-libs/aiohttp)** — Async HTTP server for GitHub webhooks
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** — Environment variable loader

---
##License

This project is licensed under the MIT License.

Copyright (c) 2026 Ashmipande-y & ACERON1301

You are free to use, copy, modify, merge, publish, distribute, sublicense, and sell copies of this software, subject to the MIT License.

