#!/usr/bin/env python3
"""Sample replies from the linked group to understand format."""
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
    
    # Get replies to recent channel posts
    count = 0
    async for msg in client.iter_messages(linked, limit=500):
        if msg.reply_to and msg.reply_to.reply_to_msg_id:
            print(f"--- Reply to post {msg.reply_to.reply_to_msg_id} ---")
            print(f"Full text:\n{msg.text[:500] if msg.text else '[no text]'}")
            print()
            count += 1
            if count >= 10:
                break
    
    await client.disconnect()

asyncio.run(main())