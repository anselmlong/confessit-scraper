#!/usr/bin/env python3
"""Scrape job channels for matching jobs."""
import asyncio
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

CHANNELS = {
    "sgtempcontractjob": "SG Temp & Contract",
    "LuxuryCareersSg": "Luxury Careers SG",
}

async def main():
    client = TelegramClient("sessions/jobScraper", API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        import shutil
        shutil.copy("sessions/nusScraper.session", "sessions/jobScraper.session")
        await client.disconnect()
        client = TelegramClient("sessions/jobScraper", API_ID, API_HASH)
        await client.connect()

    for username, title in CHANNELS.items():
        print(f"\n========== {title} (@{username}) ==========")
        try:
            entity = await client.get_entity(f"https://t.me/{username}")
            msgs = await client.get_messages(entity, limit=30)
            for m in msgs:
                if m.text:
                    text = m.text[:600]
                    print(f"\n--- [{m.id}] {m.date.strftime('%d %b %H:%M')} ---")
                    print(text)
        except Exception as e:
            print(f"  ERROR: {e}")

    await client.disconnect()

asyncio.run(main())