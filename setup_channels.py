"""
Run ONCE against your server to build the full category/channel/role structure.
python3 setup_channels.py
"""
import os
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])

STRUCTURE = {
    "INFO / ONBOARDING": ["welcome-rules", "announcements", "roadmap-milestones"],
    "GENERAL": ["general", "random"],
    "TEAM-WISE": [
        "product-strategy", "engineering-ai-ml", "fullstack-dev",
        "arvr-flutter", "iot-hardware", "cloud-infra-security",
        "ui-ux-design", "marketing-growth", "ops-admin",
    ],
    "BUSINESS": ["pilot-partners", "investor-incubation", "customer-feedback"],
    "DEV-OPS": ["bug-tracker", "deployments", "github-feed"],
}
ROLES = ["Founder", "Engineer", "Designer", "Marketing"]

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    guild = client.get_guild(GUILD_ID)
    for role_name in ROLES:
        if not discord.utils.get(guild.roles, name=role_name):
            await guild.create_role(name=role_name)
            print(f"role created: {role_name}")

    for category_name, channels in STRUCTURE.items():
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
            print(f"category created: {category_name}")
        for ch_name in channels:
            if not discord.utils.get(guild.text_channels, name=ch_name):
                await guild.create_text_channel(ch_name, category=category)
                print(f"  channel created: #{ch_name}")

    # ticket category for the bot's !ticket command
    if not discord.utils.get(guild.categories, name="TICKETS"):
        cat = await guild.create_category("TICKETS")
        print(f"category created: TICKETS (id={cat.id}) -> put this in TICKET_CATEGORY_ID")

    print("Done. Fill in .env with the channel/category IDs printed above (right-click > Copy ID).")
    await client.close()

client.run(TOKEN)
