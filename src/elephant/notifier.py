"""
Deliver the daily digest to configured channels.
Currently supports Discord. Gmail support is added when authenticated.
"""

import configparser
import logging
import os
from pathlib import Path

SECRET_DIR = Path.home() / "secret"
DISCORD_MAX_LEN = 2000


def _load_discord_config() -> tuple[str, str] | tuple[None, None]:
    path = SECRET_DIR / "discord.keys"
    if not path.exists():
        return None, None
    cfg = configparser.ConfigParser()
    cfg.read(path)
    token = cfg.get("ELEPHANT", "TOKEN", fallback=None) or cfg.get("DEFAULT", "TOKEN", fallback=None)
    channel_id = cfg.get("ELEPHANT", "CHANNEL_ID", fallback=None)
    if not token or not channel_id:
        return None, None
    return token.strip(), channel_id.strip()


def _chunk(text: str, size: int = DISCORD_MAX_LEN) -> list[str]:
    """Split text into Discord-safe chunks, breaking on newlines where possible."""
    chunks = []
    while len(text) > size:
        split_at = text.rfind("\n", 0, size)
        if split_at == -1:
            split_at = size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


async def _send_discord(token: str, channel_id: str, text: str) -> None:
    import discord

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(int(channel_id))
            if channel is None:
                channel = await client.fetch_channel(int(channel_id))
            for chunk in _chunk(text):
                await channel.send(f"```\n{chunk}\n```")
        except Exception:
            logging.exception("Discord send failed")
        finally:
            await client.close()

    await client.start(token)


def send(digest: str) -> None:
    """Send the digest to all configured channels (blocking)."""
    import asyncio

    token, channel_id = _load_discord_config()
    if token and channel_id:
        try:
            from elephant.formatter import to_markdown
            asyncio.run(_send_discord(token, channel_id, to_markdown(digest)))
            print("Digest sent to Discord.")
        except Exception:
            logging.exception("Failed to send digest to Discord")
    else:
        logging.debug("Discord not configured for ELEPHANT — skipping notification")
