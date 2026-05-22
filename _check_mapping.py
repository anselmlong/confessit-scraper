#!/usr/bin/env python3
"""Check how linked group thread roots relate to channel posts."""
import asyncio
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient, functions

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

async def main():
    client = TelegramClient("sessions/nusScraper", API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("NOT_AUTHORIZED")
        return

    linked = await client.get_entity(2136389375)
    
    # Fetch a few standalone messages (thread roots) — messages without reply_to
    count = 0
    async for msg in client.iter_messages(linked, limit=20):
        if not msg.reply_to:
            print(f"--- Thread root msg {msg.id} ---")
            print(f"  Text preview: {msg.text[:200] if msg.text else '[no text]'}")
            print(f"  Fwd from: {msg.fwd_from}")
            if msg.fwd_from:
                print(f"  Fwd from ID: {msg.fwd_from.from_id}")
            # Check if this matches a channel post
            print()
            count += 1
            if count >= 5:
                break

    # Now try the direct approach: use GetMessagesReactions or iterate channel with replies
    print("\n\n--- Channel post with replies ---")
    channel = await client.get_entity("t.me/NUSConfessIT")
    
    # Try to get comments for a specific channel post
    # Use iter_messages with reply_to set to the channel post ID
    print("Trying to get replies for channel post 72655...")
    try:
        replies = await client.get_messages(linked, reply_to=72655, limit=5)
        print(f"Got {len(replies)} replies via reply_to=72655")
        for r in replies[:3]:
            print(f"  reply {r.id}: text={r.text[:80] if r.text else '[no text]'}")
    except Exception as e:
        print(f"Error: {e}")
    
    await client.disconnect()

asyncio.run(main())