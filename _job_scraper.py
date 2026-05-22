#!/usr/bin/env python3
"""Scrape recent job postings using a separate session."""
import asyncio
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

CHANNELS = {
    "sgtempcontractjob": "🇸🇬SG TEMP & CONTRACT JOBS",
    "LuxuryCareersSg": "Luxury Careers SG",
}

async def main():
    # Use a separate session to avoid lock conflicts
    client = TelegramClient("sessions/jobScraper", API_ID, API_HASH)
    await client.connect()
    authorized = await client.is_user_authorized()
    if not authorized:
        print("Session not authorized. Copying from nusScraper...")
        await client.disconnect()
        # Copy the session file
        import shutil
        shutil.copy("sessions/nusScraper.session", "sessions/jobScraper.session")
        client = TelegramClient("sessions/jobScraper", API_ID, API_HASH)
        await client.connect()

    for username, title in CHANNELS.items():
        print(f"\n{'='*60}")
        print(f"📢 {title} (@{username})")
        print(f"{'='*60}")
        try:
            entity = await client.get_entity(f"https://t.me/{username}")
            msgs = await client.get_messages(entity, limit=15)
            for m in msgs:
                if m.text:
                    text = m.text[:400]
                    print(f"\n--- [{m.id}] {m.date.strftime('%d %b %H:%M')} ---")
                    print(text)
        except Exception as e:
            print(f"  ERROR: {e}")

    await client.disconnect()

asyncio.run(main())