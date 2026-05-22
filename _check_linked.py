#!/usr/bin/env python3
"""Check if NUSConfessIT has a linked discussion group."""
import asyncio
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient
from telethon import functions

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

async def main():
    client = TelegramClient("sessions/nusScraper", API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("NOT_AUTHORIZED")
        return
    
    channel = await client.get_entity("t.me/NUSConfessIT")
    print(f"Channel ID: {channel.id}")
    print(f"Title: {channel.title}")
    
    try:
        full = await client(functions.channels.GetFullChannelRequest(channel=channel))
        linked_id = full.full_chat.linked_chat_id
        print(f"Linked chat ID: {linked_id}")
        if linked_id and linked_id != 0:
            linked = await client.get_entity(linked_id)
            print(f"Linked group title: {linked.title}")
            print(f"Linked group ID: {linked.id}")
            total = await client.get_messages(linked, limit=0)
            print(f"Total messages in linked group: {total.total}")
            msgs = await client.get_messages(linked, limit=5)
            print("Recent messages:")
            for m in msgs:
                reply_to = m.reply_to.reply_to_msg_id if m.reply_to else None
                text_preview = (m.text or "[no text/media]")[:100]
                print(f"  msg {m.id}: reply_to_post={reply_to}, text={text_preview}")
        else:
            print("No linked discussion group.")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    
    await client.disconnect()

asyncio.run(main())
