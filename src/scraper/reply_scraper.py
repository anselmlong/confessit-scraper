"""Scrape replies from the NUSConfessIT linked discussion group.

The channel "NUS ConfessIt 📣" has a linked group "NUS ConfessIt chat"
(ID: 2136389375) where users reply to confessions. This module fetches
those reply messages and pairs them with the parent confession post.
"""

import asyncio
import os
import re

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError, AuthKeyError

from src.logger import get_logger

load_dotenv()

log = get_logger("reply_scraper")

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINKED_GROUP_ID = 2136389375  # "NUS ConfessIt chat"

# Reply format regex
_COMMENTER_RE = re.compile(r"\*\*Commenter\s*([^*]*):\*\*\s*")
_VOTE_FOOTER_RE = re.compile(r"\*\*\s*(\d+)\s*\S*\s*\|\s*(\d+)\s*\S*\s*\*\*")


def _validate_credentials():
    missing = [k for k, v in {"TELEGRAM_API_ID": API_ID, "TELEGRAM_API_HASH": API_HASH}.items() if not v]
    if missing:
        raise ValueError(
            f"Missing credentials in .env: {', '.join(missing)}\n"
            "Check that TELEGRAM_API_ID and TELEGRAM_API_HASH are set."
        )
    try:
        int(API_ID)
    except (TypeError, ValueError):
        raise ValueError(f"TELEGRAM_API_ID must be a number, got: {API_ID!r}")


def parse_reply(raw_text: str) -> dict:
    """Parse reply text into {author, text, reactions_up, reactions_down}.

    Format:
        **Commenter EMOJI:**
        <body text>

        **X 🇸🇬 | Y 👎**
    """
    if not raw_text:
        return {"author": None, "text": None, "reactions_up": 0, "reactions_down": 0}

    result = {"author": None, "text": None, "reactions_up": 0, "reactions_down": 0}

    # Extract votes footer first
    vote_match = _VOTE_FOOTER_RE.search(raw_text)
    if vote_match:
        result["reactions_up"] = int(vote_match.group(1))
        result["reactions_down"] = int(vote_match.group(2))
        body = raw_text[: vote_match.start()].strip()
    else:
        body = raw_text.strip()

    # Extract author
    author_match = _COMMENTER_RE.match(body)
    if author_match:
        author_raw = author_match.group(1).strip()
        result["author"] = author_raw if author_raw else None
        body = body[author_match.end():].strip()

    result["text"] = body if body else None
    return result


async def _resolve_channel_post_id(
    client: TelegramClient,
    entity,
    group_root_id: int,
    cache: dict[int, int],
) -> int | None:
    """Resolve a linked-group root message ID to its channel post ID.

    Thread roots in the linked group are auto-forwards of channel posts.
    They carry fwd_from.channel_post which is the actual channel post ID.
    Uses an in-memory cache (group_root_id → channel_post_id) to avoid
    re-fetching the same root message.
    """
    if group_root_id in cache:
        return cache[group_root_id]

    try:
        root_msg = await client.get_messages(entity, ids=group_root_id)
        if root_msg and root_msg.fwd_from and root_msg.fwd_from.channel_post:
            channel_post_id = root_msg.fwd_from.channel_post
            cache[group_root_id] = channel_post_id
            return channel_post_id
    except Exception as e:
        log.warning("Failed to resolve group root %d: %s", group_root_id, e)

    cache[group_root_id] = None  # mark as unresolvable
    return None


def _flush_batch(batch: list[dict], total_saved: int) -> int:
    """Save a batch of replies to DB and clear the buffer."""
    if not batch:
        return total_saved
    # Lazy import to avoid circular dependency
    from src.storage.db import save_replies
    saved = save_replies(batch)
    batch.clear()
    new_total = total_saved + saved
    log.info("Flushed batch: %d saved (%d total)", saved, new_total)
    return new_total


async def _scrape_replies_async(
    limit: int = None,
    since_msg_id: int = 0,
    max_msg_id: int = 0,
    batch_size: int = 5000,
    progress_callback=None,
) -> int:
    """Fetch replies from the linked discussion group, saving in batches.

    Args:
        limit: Max replies to fetch (None = all matching).
        since_msg_id: Only messages with ID > this (forward incremental).
        max_msg_id: Only messages with ID <= this (backfill continuation).
        batch_size: Flush to DB every N replies.

    Returns the total number of replies saved to the database.
    """
    _validate_credentials()

    sessions_dir = os.path.join(_PROJECT_ROOT, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, "nusScraper")

    log.info("Connecting to Telegram for reply scraping...")
    client = TelegramClient(session_path, int(API_ID), API_HASH)
    batch = []
    total_saved = 0
    collected = 0
    root_cache: dict[int, int] = {}

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

        log.info("Connected. Fetching replies from linked group (min_id=%s, max_id=%s)...",
                 since_msg_id or "0", max_msg_id or "max")

        try:
            entity = await client.get_entity(LINKED_GROUP_ID)

            async for msg in client.iter_messages(
                entity,
                limit=limit,
                min_id=since_msg_id,
                max_id=max_msg_id if max_msg_id else None,
            ):
                if not msg.reply_to or not msg.reply_to.reply_to_msg_id:
                    continue
                if not msg.text:
                    continue

                parsed = parse_reply(msg.text)
                group_root_id = getattr(msg.reply_to, "reply_to_top_id", None) or msg.reply_to.reply_to_msg_id

                channel_post_id = await _resolve_channel_post_id(
                    client, entity, group_root_id, root_cache
                )

                batch.append({
                    "reply_msg_id": msg.id,
                    "linked_parent_id": msg.reply_to.reply_to_msg_id,
                    "post_id": channel_post_id or group_root_id,
                    "date": msg.date.isoformat(),
                    "text": parsed["text"],
                    "author": parsed["author"],
                    "reactions_up": parsed["reactions_up"],
                    "reactions_down": parsed["reactions_down"],
                })
                collected += 1

                if len(batch) >= batch_size:
                    total_saved = _flush_batch(batch, total_saved)
                    log.info("Progress: %d collected, %d saved, %d cache entries",
                             collected, total_saved, len(root_cache))

                if progress_callback and collected % 200 == 0:
                    progress_callback(collected)

                await asyncio.sleep(0.05)

        except FloodWaitError as e:
            log.warning("Flood wait — waiting %d seconds...", e.seconds)
            for remaining in range(e.seconds, 0, -5):
                log.debug("Flood wait: %ds remaining", remaining)
                await asyncio.sleep(min(5, remaining))
            log.info("Retrying after flood wait.")

    except (ConnectionError, OSError) as e:
        raise RuntimeError(f"Network error: {e}\nCheck your internet connection.") from e
    finally:
        # Flush remaining batch
        if batch:
            total_saved = _flush_batch(batch, total_saved)
        await client.disconnect()

    log.info("Reply scrape complete: %d collected, %d saved, %d cache entries.",
             collected, total_saved, len(root_cache))
    return total_saved


def scrape_replies(
    limit: int = None,
    since_msg_id: int = 0,
    max_msg_id: int = 0,
    batch_size: int = 5000,
    progress_callback=None,
) -> int:
    """Synchronous entry point for scraping replies.

    Returns total number of replies saved to the database.
    """
    return asyncio.run(
        _scrape_replies_async(
            limit=limit,
            since_msg_id=since_msg_id,
            max_msg_id=max_msg_id,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )
    )