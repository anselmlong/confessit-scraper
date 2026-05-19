#!/usr/bin/env python3
"""Check reply message structure in linked group."""
import asyncio
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

async def main():
    client = TelegramClient("sessions/nusScraper", API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("NOT_AUTHORIZED")
        return
    
    linked = await client.get_entity(2136389375)
    
    # Get messages that are replies (with reply_to set)
    msgs = await client.get_messages(linked, limit=20)
    for m in msgs:
        r = m.reply_to
        if r:
            print(f"msg {m.id}:")
            print(f"  reply_to type: {type(r).__name__}")
            # Print all attributes
            for attr in dir(r):
                if not attr.startswith('_'):
                    val = getattr(r, attr)
                    if not callable(val):
                        print(f"  reply_to.{attr} = {val!r}")
            print(f"  text preview: {(m.text or '')[:150]}")
            print()
    
    await client.disconnect()

asyncio.run(main())
