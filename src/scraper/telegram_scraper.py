import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")


def _count_reactions(message) -> int:
    if not message.reactions:
        return 0
    return sum(r.count for r in message.reactions.results)


async def _scrape_channel_async(channel_url: str, limit: int = None, since_id: int = 0) -> list[dict]:
    if not API_ID or not API_HASH:
        raise ValueError(
            "Missing TELEGRAM_API_ID or TELEGRAM_API_HASH. "
            "Copy .env.example to .env and fill in your credentials from https://my.telegram.org"
        )

    sessions_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "sessions",
    )
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, "nusScraper")

    client = TelegramClient(session_path, int(API_ID), API_HASH)
    messages = []

    async with client:
        await client.start(phone=PHONE)
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
            await asyncio.sleep(0.05)

    return messages


def scrape_channel(channel_url: str, limit: int = None, since_id: int = 0) -> list[dict]:
    return asyncio.run(_scrape_channel_async(channel_url, limit=limit, since_id=since_id))
