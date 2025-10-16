#!/usr/bin/env python3
"""
Discord bot that watches the public (WAN) IP address of the host.
- Sends a message to a configured channel whenever the IP changes.
- Responds to the "!myip" command with the current IP.
"""

import asyncio
import time
import logging
import os
from typing import Optional

import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ------------------------------------------------------------
# Load configuration ------------------------------------------------
# ------------------------------------------------------------
load_dotenv()  # pulls from .env if present

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set in environment or .env file")

# Channel where change‑notifications will be posted
CHANNEL_ID_STR = os.getenv("NOTIFY_CHANNEL_ID")
if not CHANNEL_ID_STR:
    raise RuntimeError("NOTIFY_CHANNEL_ID not set")
NOTIFY_CHANNEL_ID = int(CHANNEL_ID_STR)

# How often we poll the IP service (seconds)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # default 5 min

# ------------------------------------------------------------
# Logging ---------------------------------------------------------
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------
# Helper: fetch public IP ------------------------------------------
# ------------------------------------------------------------
IP_SERVICE_URL = "https://api.ipify.org?format=text"

async def fetch_public_ip(session: aiohttp.ClientSession) -> Optional[str]:
    """Return the current public IPv4 address as a string, or None on failure."""
    try:
        async with session.get(IP_SERVICE_URL, timeout=10) as resp:
            resp.raise_for_status()
            ip = (await resp.text()).strip()
            return ip
    except Exception as exc:
        log.warning(f"Failed to fetch public IP: {exc}")
        return None

# ------------------------------------------------------------
# Bot setup -------------------------------------------------------
# ------------------------------------------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ------------------------------------------------------------
# State persistence ------------------------------------------------
# ------------------------------------------------------------
STATE_FILE = "last_ip.txt"

def load_last_ip() -> Optional[str]:
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    return None

def save_last_ip(ip: str) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(ip)


# ------------------------------------------------------------
# Background task: monitor IP ---------------------------------------
# ------------------------------------------------------------
@tasks.loop(seconds=CHECK_INTERVAL)
async def ip_monitor():
    async with aiohttp.ClientSession() as session:
        current_ip = await fetch_public_ip(session)

    if current_ip is None:
        return  # keep old value, try again next loop

    last_ip = load_last_ip()
    if last_ip != current_ip:
        # IP changed (or first run)
        save_last_ip(current_ip)
        channel = bot.get_channel(NOTIFY_CHANNEL_ID)
        if channel:
            if last_ip is None:
                msg = f"🟢 Bot started – current public IP is **{current_ip}**."
            else:
                msg = f"⚠️ Public IP **changed** from `{last_ip}` to **{current_ip}**."
            await channel.send(msg)
            log.info(msg)
        else:
            log.error(f"Could not find channel with ID {NOTIFY_CHANNEL_ID}")
    else:
        log.debug("IP unchanged.")

# ------------------------------------------------------------
# Bot events -------------------------------------------------------
# ------------------------------------------------------------
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if not ip_monitor.is_running():
        ip_monitor.start()
    log.info("IP monitor task started.")


# ------------------------------------------------------------
# Entry point ------------------------------------------------------
# ------------------------------------------------------------
if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("Shutting down by user request.")