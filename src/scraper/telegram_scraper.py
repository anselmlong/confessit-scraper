import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    AuthKeyError,
    FloodWaitError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
    UsernameInvalidError,
)

from src.logger import get_logger

load_dotenv()

log = get_logger("scraper")

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _count_reactions(message) -> int:
    if not message.reactions:
        return 0
    return sum(r.count for r in message.reactions.results)


def _validate_credentials():
    missing = [k for k, v in {"TELEGRAM_API_ID": API_ID, "TELEGRAM_API_HASH": API_HASH}.items() if not v]
    if missing:
        raise ValueError(
            f"Missing credentials in .env: {', '.join(missing)}\n"
            "  1. Copy .env.example to .env\n"
            "  2. Get your API ID and hash from https://my.telegram.org\n"
            "  3. Fill them in and try again."
        )
    try:
        int(API_ID)
    except (TypeError, ValueError):
        raise ValueError(f"TELEGRAM_API_ID must be a number, got: {API_ID!r}")


async def _scrape_channel_async(
    channel_url: str,
    limit: int = None,
    since_id: int = 0,
    progress_callback=None,
) -> list[dict]:
    _validate_credentials()

    sessions_dir = os.path.join(_PROJECT_ROOT, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, "nusScraper")

    log.info("Connecting to Telegram...")
    client = TelegramClient(session_path, int(API_ID), API_HASH)
    messages = []

    try:
        async with client:
            try:
                await client.start(phone=PHONE)
            except PhoneNumberInvalidError:
                raise ValueError(
                    f"Phone number {PHONE!r} is invalid. "
                    "Set TELEGRAM_PHONE in .env in international format, e.g. +6512345678"
                )
            except SessionPasswordNeededError:
                raise RuntimeError(
                    "Your Telegram account has two-step verification enabled. "
                    "Delete sessions/nusScraper.session and re-run to enter your password."
                )
            except AuthKeyError:
                raise RuntimeError(
                    "Telegram auth key is invalid or expired. "
                    "Delete sessions/nusScraper.session and re-run to log in again."
                )

            log.info("Connected. Fetching messages from %s (since_id=%d)...", channel_url, since_id)

            try:
                async for msg in client.iter_messages(channel_url, limit=limit, min_id=since_id):
                    if not msg.text:
                        continue

                    messages.append({
                        "id": msg.id,
                        "date": msg.date.isoformat(),
                        "text": msg.text,
                        "views": msg.views or 0,
                        "forwards": msg.forwards or 0,
                        "reactions_count": _count_reactions(msg),
                        "reply_count": msg.replies.replies if msg.replies else 0,
                        "is_reply": msg.reply_to is not None,
                        "reply_to_msg_id": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
                    })

                    if len(messages) % 100 == 0:
                        log.debug("Fetched %d messages so far...", len(messages))

                    if progress_callback:
                        progress_callback(len(messages))

                    await asyncio.sleep(0.05)

            except FloodWaitError as e:
                log.warning("Telegram rate limit hit — waiting %d seconds before retrying...", e.seconds)
                for remaining in range(e.seconds, 0, -5):
                    log.debug("Flood wait: %d seconds remaining", remaining)
                    await asyncio.sleep(min(5, remaining))
                log.info("Retrying after flood wait. %d messages collected so far.", len(messages))

            except UsernameInvalidError:
                raise ValueError(
                    f"Channel not found: {channel_url!r}\n"
                    "Check that the channel URL is correct and publicly accessible."
                )

    except (ConnectionError, OSError) as e:
        raise RuntimeError(
            f"Network error while connecting to Telegram: {e}\n"
            "Check your internet connection and try again."
        ) from e

    log.info("Scrape complete: %d messages fetched.", len(messages))
    return messages


def scrape_channel(
    channel_url: str,
    limit: int = None,
    since_id: int = 0,
    progress_callback=None,
) -> list[dict]:
    return asyncio.run(
        _scrape_channel_async(channel_url, limit=limit, since_id=since_id, progress_callback=progress_callback)
    )
