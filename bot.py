import os
import time
import asyncio
import discord
from discord.ext import commands, tasks
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
ADMIN_PIN = os.environ.get("ADMIN_PIN", "")
ADMIN_SESSION_MINUTES = int(os.environ.get("ADMIN_SESSION_MINUTES", "15"))
MEETINGS_CHANNEL_ID = int(os.environ.get("MEETINGS_CHANNEL_ID", "0"))
GITHUB_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_FEED_CHANNEL_ID = int(os.environ.get("GITHUB_FEED_CHANNEL_ID", "0"))
MOD_LOG_CHANNEL_ID = int(os.environ.get("MOD_LOG_CHANNEL_ID", "0"))
STANDUP_CHANNEL_ID = int(os.environ.get("STANDUP_CHANNEL_ID", "0"))
WELCOME_CHANNEL_ID = int(os.environ.get("WELCOME_CHANNEL_ID", "0"))
TICKET_CATEGORY_ID = int(os.environ.get("TICKET_CATEGORY_ID", "0"))
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "8080"))

# role name -> emoji, for role-select message in #welcome-rules
ROLE_MAP = {
    "🧠": "Founder",
    "🛠️": "Engineer",
    "🎨": "Designer",
    "📈": "Marketing",
}
ROLE_SELECT_MESSAGE_ID = int(os.environ.get("ROLE_SELECT_MESSAGE_ID", "0"))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="CraneBot — Commands", color=0x2b2d31)
    embed.add_field(name="!ticket <topic>", value="Open a private ticket channel", inline=False)
    embed.add_field(name="!close", value="Close the current ticket (inside a ticket-* channel)", inline=False)
    embed.add_field(name="!remind <minutes> <text>", value="DM-free reminder ping in this channel", inline=False)
    embed.add_field(name="!kick <@member> [reason]", value="Kick a member — requires Kick Members perm", inline=False)
    embed.add_field(name="!purge <amount>", value="Bulk delete messages — requires Manage Messages perm", inline=False)
    embed.add_field(name="🔒 Admin mode", value="`!admin <pin>` unlocks below for {} min · `!lock` locks early".format(ADMIN_SESSION_MINUTES), inline=False)
    embed.add_field(name="!schedule <date> <time> <topic>", value="Admin-only. Posts a meeting announcement", inline=False)
    embed.add_field(name="!meetlink <url> [label]", value="Admin-only. Posts the meeting link", inline=False)
    embed.add_field(name="!ban <@member> [reason]", value="Admin-only + requires Ban Members perm", inline=False)
    embed.add_field(name="Role reactions", value="React 🧠 Founder · 🛠️ Engineer · 🎨 Designer · 📈 Marketing on the pinned message in #welcome-rules", inline=False)
    embed.add_field(name="GitHub feed", value="Automatic — commits/PRs/issues post to #github-feed, no command needed", inline=False)
    embed.add_field(name="Daily standup", value="Automatic — bot pings the standup channel every 24h", inline=False)
    await ctx.send(embed=embed)

# ---------------------------------------------------------------------------
# Welcome + auto-role
# ---------------------------------------------------------------------------

@bot.event
async def on_member_join(member: discord.Member):
    ch = bot.get_channel(WELCOME_CHANNEL_ID)
    if ch:
        await ch.send(
            f"Welcome {member.mention}! React in this channel "
            f"to grab a role: 🧠 Founder · 🛠️ Engineer · 🎨 Designer · 📈 Marketing"
        )

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.message_id != ROLE_SELECT_MESSAGE_ID or payload.user_id == bot.user.id:
        return
    role_name = ROLE_MAP.get(str(payload.emoji))
    if not role_name:
        return
    guild = bot.get_guild(payload.guild_id)
    role = discord.utils.get(guild.roles, name=role_name)
    member = guild.get_member(payload.user_id)
    if role and member:
        await member.add_roles(role, reason="self-assigned via reaction")

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.message_id != ROLE_SELECT_MESSAGE_ID:
        return
    role_name = ROLE_MAP.get(str(payload.emoji))
    if not role_name:
        return
    guild = bot.get_guild(payload.guild_id)
    role = discord.utils.get(guild.roles, name=role_name)
    member = guild.get_member(payload.user_id)
    if role and member:
        await member.remove_roles(role, reason="self-unassigned via reaction")

# ---------------------------------------------------------------------------
# Private/admin mode — PIN-gated session, unlocks meeting + ban commands
# ---------------------------------------------------------------------------

_admin_sessions = {}  # user_id -> expiry unix timestamp

def is_admin_unlocked(user_id: int) -> bool:
    expiry = _admin_sessions.get(user_id)
    return expiry is not None and time.time() < expiry

def requires_admin_pin():
    async def predicate(ctx):
        if not is_admin_unlocked(ctx.author.id):
            await ctx.send(
                f"{ctx.author.mention} locked. Unlock with `!admin <pin>` first "
                f"(DM me the pin if you don't want it visible in-channel).",
                delete_after=8,
            )
            return False
        return True
    return commands.check(predicate)

@bot.command()
async def admin(ctx, pin: str = None):
    # delete the invoking message if it leaked the pin into a public channel
    if isinstance(ctx.channel, discord.TextChannel):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    if not ADMIN_PIN:
        await ctx.send("ADMIN_PIN not configured on the server.", delete_after=6)
        return
    if pin != ADMIN_PIN:
        await ctx.send(f"{ctx.author.mention} wrong pin.", delete_after=6)
        return

    _admin_sessions[ctx.author.id] = time.time() + ADMIN_SESSION_MINUTES * 60
    try:
        await ctx.author.send(f"Admin mode unlocked for {ADMIN_SESSION_MINUTES} minutes.")
        await ctx.send(f"{ctx.author.mention} unlocked (check DMs).", delete_after=6)
    except discord.Forbidden:
        await ctx.send(f"{ctx.author.mention} unlocked for {ADMIN_SESSION_MINUTES} minutes.", delete_after=6)

@bot.command()
async def lock(ctx):
    _admin_sessions.pop(ctx.author.id, None)
    await ctx.send(f"{ctx.author.mention} locked.", delete_after=5)

# ---------------------------------------------------------------------------
# Meeting scheduling / link — admin-only
# ---------------------------------------------------------------------------

@bot.command()
@requires_admin_pin()
async def schedule(ctx, date: str, time_: str, *, topic="Team sync"):
    """!schedule 2026-09-02 18:00 Sprint review"""
    ch = bot.get_channel(MEETINGS_CHANNEL_ID) or ctx.channel
    await ch.send(f"📅 **{topic}** — {date} {time_} (set by {ctx.author.display_name})")
    await ctx.send("Meeting scheduled.", delete_after=5)

@bot.command()
@requires_admin_pin()
async def meetlink(ctx, url: str, *, label="Join here"):
    ch = bot.get_channel(MEETINGS_CHANNEL_ID) or ctx.channel
    await ch.send(f"🔗 **{label}**: {url}")
    await ctx.send("Link posted.", delete_after=5)

# ---------------------------------------------------------------------------
# Moderation — bare minimum
# ---------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason given"):
    await member.kick(reason=reason)
    await ctx.send(f"Kicked {member}. Reason: {reason}")
    await log_mod(f"🥾 {ctx.author} kicked {member} — {reason}")

@bot.command()
@requires_admin_pin()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason given"):
    await member.ban(reason=reason)
    await ctx.send(f"Banned {member}. Reason: {reason}")
    await log_mod(f"🔨 {ctx.author} banned {member} — {reason}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int = 10):
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"Deleted {len(deleted) - 1} messages.")
    await asyncio.sleep(3)
    await msg.delete()

async def log_mod(text: str):
    ch = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if ch:
        await ch.send(text)

# ---------------------------------------------------------------------------
# Ticket Tool — !ticket opens a private channel for pilot partner / customer
# ---------------------------------------------------------------------------

@bot.command()
async def ticket(ctx, *, topic="support"):
    category = bot.get_channel(TICKET_CATEGORY_ID)
    guild = ctx.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    ch_name = f"ticket-{ctx.author.name}".lower().replace(" ", "-")
    channel = await guild.create_text_channel(
        ch_name, category=category, overwrites=overwrites,
        topic=f"Opened by {ctx.author} — {topic}"
    )
    await channel.send(f"{ctx.author.mention} ticket opened: **{topic}**. A team member will follow up here.")
    await ctx.send(f"Ticket created: {channel.mention}", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def close(ctx):
    if ctx.channel.name.startswith("ticket-"):
        await ctx.send("Closing ticket in 5s.")
        await asyncio.sleep(5)
        await ctx.channel.delete()

# ---------------------------------------------------------------------------
# Standup / reminder — daily ping, no external scheduler
# ---------------------------------------------------------------------------

@tasks.loop(hours=24)
async def daily_standup():
    ch = bot.get_channel(STANDUP_CHANNEL_ID)
    if ch:
        await ch.send("⏰ Daily standup: drop your update (yesterday / today / blockers).")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def remind(ctx, minutes: int, *, text):
    await ctx.send(f"Reminder set for {minutes}m.")
    await asyncio.sleep(minutes * 60)
    await ctx.send(f"⏰ {ctx.author.mention} — {text}")

# ---------------------------------------------------------------------------
# GitHub webhook -> #github-feed  (aiohttp server sharing the bot's event loop)
# ---------------------------------------------------------------------------

async def github_webhook(request: web.Request):
    if GITHUB_SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        body = await request.read()
        import hmac, hashlib
        expected = "sha256=" + hmac.new(GITHUB_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return web.Response(status=401, text="bad signature")
        payload = await request.json()
    else:
        payload = await request.json()

    event = request.headers.get("X-GitHub-Event", "unknown")
    text = format_github_event(event, payload)
    ch = bot.get_channel(GITHUB_FEED_CHANNEL_ID)
    if ch and text:
        await ch.send(text)
    return web.Response(text="ok")

def format_github_event(event, p):
    repo = p.get("repository", {}).get("full_name", "repo")
    if event == "push":
        commits = p.get("commits", [])
        pusher = p.get("pusher", {}).get("name", "someone")
        lines = "\n".join(f"- {c['message'].splitlines()[0]}" for c in commits[:5])
        return f"📦 **{pusher}** pushed {len(commits)} commit(s) to `{repo}`\n{lines}"
    if event == "pull_request":
        action = p.get("action")
        pr = p.get("pull_request", {})
        return f"🔀 PR {action}: **{pr.get('title')}** in `{repo}` by {p.get('sender',{}).get('login')}\n{pr.get('html_url')}"
    if event == "issues":
        action = p.get("action")
        issue = p.get("issue", {})
        return f"🐛 Issue {action}: **{issue.get('title')}** in `{repo}`\n{issue.get('html_url')}"
    return None

async def start_webhook_server():
    app = web.Application()
    app.router.add_post("/github", github_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()

# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    if bot.user.name != "CraneBot":
        try:
            await bot.user.edit(username="CraneBot")
        except discord.HTTPException as e:
            print(f"couldn't rename (rate-limited, max 2/hour): {e}")
    if not daily_standup.is_running():
        daily_standup.start()
    await start_webhook_server()
    print(f"GitHub webhook listening on :{WEBHOOK_PORT}/github")

bot.run(TOKEN)
