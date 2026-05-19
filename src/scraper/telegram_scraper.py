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
        await client.connect()
        try:
            if not await client.is_user_authorized():
                raise RuntimeError(
                    "Not logged in to Telegram.\n"
                    "Run  python auth.py  once to complete sign-in, then retry."
                )
        except AuthKeyError:
            raise RuntimeError(
                "Telegram auth key is invalid or expired.\n"
                "Delete sessions/nusScraper.session, run  python auth.py  to log in again."
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
    finally:
        await client.disconnect()

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


async def _scrape_replies_async(
    channel_url: str,
    group_id: int = None,
    limit: int = None,
    since_id: int = 0,
    progress_callback=None,
) -> list[dict]:
    """Scrape replies from the linked discussion group of a Telegram channel.

    Returns a list of reply dicts with keys:
        post_id, linked_parent_id, reply_msg_id, date, text,
        author, reactions_up, reactions_down
    """
    _validate_credentials()

    sessions_dir = os.path.join(_PROJECT_ROOT, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, "nusScraper")

    log.info("Connecting to Telegram...")
    client = TelegramClient(session_path, int(API_ID), API_HASH)
    replies = []

    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Not logged in to Telegram.\n"
                "Run  python auth.py  once to complete sign-in, then retry."
            )

        # Resolve the linked discussion group if not given directly
        if group_id:
            linked = await client.get_entity(group_id)
        else:
            channel = await client.get_entity(channel_url)
            from telethon import functions
            full = await client(functions.channels.GetFullChannelRequest(channel=channel))
            linked_id = full.full_chat.linked_chat_id
            if not linked_id:
                raise ValueError(f"Channel {channel_url} has no linked discussion group.")
            linked = await client.get_entity(linked_id)
            log.info("Linked group: %s (ID: %d)", linked.title, linked.id)

        log.info("Fetching messages from linked group (since_id=%d)...", since_id)

        try:
            async for msg in client.iter_messages(linked, limit=limit, min_id=since_id):
                if not msg.text:
                    continue

                # Only process messages that are replies (have reply_to)
                if not msg.reply_to:
                    continue

                parent_id = msg.reply_to.reply_to_msg_id
                if not parent_id:
                    continue

                # Parse the reply format:
                # **Commenter <emoji>:**
                # <text>
                #
                # **<up> 🇸🇬 | <down> 👎**
                text = msg.text
                author = None
                reactions_up = 0
                reactions_down = 0

                # Extract author from the first line
                lines = text.split("\n")
                if lines and lines[0].startswith("**Commenter"):
                    author = lines[0].strip("*").strip()
                    reply_body = "\n".join(lines[1:]).strip()
                else:
                    reply_body = text

                # Extract upvote/downvote from the last line
                last_line = lines[-1].strip() if lines else ""
                import re
                vote_match = re.search(r'\*\*(\d+)\s*[🇸🇬]+\s*\|\s*(\d+)\s*👎\*\*', last_line)
                if vote_match:
                    reactions_up = int(vote_match.group(1))
                    reactions_down = int(vote_match.group(2))
                    # Remove the vote line from reply body
                    reply_body = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else ""

                replies.append({
                    "linked_parent_id": parent_id,
                    "reply_msg_id": msg.id,
                    "date": msg.date.isoformat(),
                    "text": reply_body or text,
                    "author": author,
                    "reactions_up": reactions_up,
                    "reactions_down": reactions_down,
                })

                if len(replies) % 100 == 0:
                    log.debug("Collected %d replies so far...", len(replies))

                if progress_callback:
                    progress_callback(len(replies))

                await asyncio.sleep(0.05)

        except FloodWaitError as e:
            log.warning("Rate limit hit — waiting %d seconds...", e.seconds)
            for remaining in range(e.seconds, 0, -5):
                log.debug("Flood wait: %d seconds remaining", remaining)
                await asyncio.sleep(min(5, remaining))
            log.info("Retrying after flood wait. %d replies collected.", len(replies))

    except UsernameInvalidError:
        raise ValueError(f"Channel not found: {channel_url!r}")
    except (ConnectionError, OSError) as e:
        raise RuntimeError(f"Network error: {e}") from e
    finally:
        await client.disconnect()

    log.info("Reply scrape complete: %d replies collected.", len(replies))
    return replies


def scrape_replies(
    channel_url: str = "t.me/NUSConfessIT",
    group_id: int = None,
    limit: int = None,
    since_id: int = 0,
    progress_callback=None,
) -> list[dict]:
    """Scrape replies from the linked discussion group.

    Args:
        channel_url: The main channel URL (used to find the linked group).
        group_id: Direct linked group ID (bypasses channel lookup).
        limit: Max messages to fetch (None = all).
        since_id: Only fetch messages newer than this ID (for incremental).
        progress_callback: Optional callback(reply_count_so_far).
    """
    return asyncio.run(
        _scrape_replies_async(
            channel_url, group_id=group_id, limit=limit,
            since_id=since_id, progress_callback=progress_callback
        )
    )
