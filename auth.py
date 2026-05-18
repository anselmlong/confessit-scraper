#!/usr/bin/env python3
"""Two-step Telegram login for non-interactive environments.

  Step 1 — send the OTP:            python auth.py
  Step 2 — enter the code:          python auth.py --code 12345
  Step 2b (if 2FA enabled):         python auth.py --code 12345 --password YOUR_2FA_PASSWORD
"""
import argparse
import asyncio
import json
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SESSION_PATH = os.path.join(_PROJECT_ROOT, "sessions", "nusScraper")
_HASH_FILE = os.path.join(_PROJECT_ROOT, "sessions", ".pending_hash")


async def send_code():
    os.makedirs(os.path.join(_PROJECT_ROOT, "sessions"), exist_ok=True)
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()
    result = await client.send_code_request(PHONE)
    with open(_HASH_FILE, "w") as f:
        json.dump({"phone_code_hash": result.phone_code_hash}, f)
    await client.disconnect()
    print(f"OTP sent to {PHONE}.")
    print(f"Now run:  python auth.py --code <the code>")


async def sign_in(code: str, password: str = None):
    if not os.path.exists(_HASH_FILE):
        print("No pending auth. Run  python auth.py  first to request a code.")
        return
    with open(_HASH_FILE) as f:
        phone_code_hash = json.load(f)["phone_code_hash"]

    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(PHONE, code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        if not password:
            print("\n2FA is enabled on your account.")
            print("Re-run with your Telegram cloud password:")
            print(f"  python auth.py --code {code} --password YOUR_2FA_PASSWORD")
            await client.disconnect()
            return
        await client.sign_in(password=password)
    me = await client.get_me()
    await client.disconnect()

    os.remove(_HASH_FILE)
    print(f"\nSigned in as: {me.first_name} (@{me.username})")
    print("Session saved. You can now run  python scrape.py  without prompts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram one-time auth")
    parser.add_argument("--code", help="OTP code received on your phone")
    parser.add_argument("--password", help="Telegram 2FA cloud password (if enabled)")
    args = parser.parse_args()

    if args.code:
        asyncio.run(sign_in(args.code, args.password))
    else:
        asyncio.run(send_code())
