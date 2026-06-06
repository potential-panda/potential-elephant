"""
Deliver the daily digest and dives to Discord.

Supports both webhook URLs and bot tokens. Webhook is simpler and recommended.

Setup — add to ~/secret/discord.keys under [ELEPHANT] or [DEFAULT]:
  TOKEN = https://discord.com/api/webhooks/{id}/{token}   ← webhook URL
  or
  TOKEN = <bot token>
  CHANNEL_ID = <channel id>   ← only needed for bot tokens
"""

import configparser
import logging
from pathlib import Path

SECRET_DIR = Path.home() / "secret"
DISCORD_MAX_LEN = 1900  # leave room for code fence markers


def _load_discord_config() -> tuple[str, str | None]:
    """Return (token_or_webhook_url, channel_id_or_None)."""
    path = SECRET_DIR / "discord.keys"
    if not path.exists():
        return None, None
    cfg = configparser.ConfigParser()
    cfg.read(path)
    for section in ("ELEPHANT", "DEFAULT"):
        token = cfg.get(section, "TOKEN", fallback=None)
        if not token:
            continue
        token = token.strip()
        channel_id = cfg.get(section, "CHANNEL_ID", fallback="").strip() or None
        return token, channel_id
    return None, None


def _chunk(text: str, size: int = DISCORD_MAX_LEN) -> list[str]:
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


def _send_webhook(webhook_url: str, text: str) -> None:
    import urllib.request, urllib.parse, json
    for chunk in _chunk(text):
        payload = json.dumps({"content": f"```\n{chunk}\n```"}).encode()
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"Webhook returned {resp.status}")


async def _send_bot(token: str, channel_id: str, text: str) -> None:
    import discord
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
            for chunk in _chunk(text):
                await channel.send(f"```\n{chunk}\n```")
        except Exception:
            logging.exception("Discord bot send failed")
        finally:
            await client.close()

    await client.start(token)


def send(text: str) -> None:
    """Send text to Discord. Detects webhook vs bot token automatically."""
    import asyncio
    from elephant.formatter import to_markdown

    token, channel_id = _load_discord_config()
    if not token:
        logging.debug("Discord not configured — skipping notification")
        return

    content = to_markdown(text)
    try:
        if token.startswith("https://"):
            _send_webhook(token, content)
        else:
            if not channel_id:
                logging.warning("Discord bot token set but no CHANNEL_ID — skipping")
                return
            asyncio.run(_send_bot(token, channel_id, content))
        print("Sent to Discord.")
    except Exception:
        logging.exception("Failed to send to Discord")
