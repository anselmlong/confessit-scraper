HANDOFF CONTEXT
===============

PROJECT
-------
confessit-scraper — scrapes t.me/NUSConfessIT, stores in SQLite, generates daily HTML reports with sentiment analysis, topic classification, and LLM summaries.

LOCATION
--------
/home/ubuntu/confessit-scraper
Python venv: /home/ubuntu/confessit-scraper/venv

WHAT WAS DONE
-------------
1. Database migration — added 4 columns to messages table:
   - category TEXT, confession_id TEXT, title TEXT, content TEXT
   - migration is idempotent (handled in db.py _migrate_v2)

2. Parser module — src/parsing/parser.py
   - parse_confession(text) → extracts category, confession_id, title, content
   - parse_batch(messages) → processes list of messages in-place
   - Regex-based, handles emojis, markdown formatting, missing fields

3. LLM summarizer — src/analysis/llm_summarizer.py
   - summarize_day(messages) → 3-5 bullet vibe summary via GPT-4o-mini
   - Uses OPENAI_API_KEY from .env
   - Chunks content to 8000 chars max, graceful fallback on failure

4. Wired everything into the pipeline:
   - scrape.py: imports parse_batch, calls it after process_messages
   - report.py: imports summarize_day + top_engaged_messages, calls both
   - report.py: passes llm_summary + top_posts to generate_daily_report()
   - src/reporting/report.py: accepts llm_summary + top_posts params
   - template.html: added "AI Vibe Check" section + "Top Posts" section

5. All Python files compile clean (verified with py_compile)

WHAT'S BROKEN
-------------
Telethon auth fails non-interactively. scrape.py --limit 50 errors with:
  "Please enter your phone (or bot token):"
  EOFError: EOF when reading a line

.env has all creds correctly:
  TELEGRAM_API_ID=23301780
  TELEGRAM_API_HASH=<set>
  TELEGRAM_PHONE=<set, valid +65 number>
  OPENAI_API_KEY=<set>

Verified env vars load correctly via python-dotenv (all four print fine).
The error is at telegram_scraper.py line 68: await client.start(phone=PHONE)
Telethon's client.start() is treating phone as callable/lambda despite PHONE
being a valid string. This is likely a telethon 1.43.2 quirk — the default
phone param in TelegramClient.start() is a lambda that calls input(), and
somehow passing phone=<string> doesn't override it.

WHAT NEEDS TO HAPPEN
--------------------
1. Fix telethon auth to work without stdin prompt
   - Check if client.start() API changed in telethon 1.43
   - Alternative: try client.send_code_request(phone) + client.sign_in() manually
   - Or: pass phone as a lambda that returns the string: phone=lambda: PHONE
   - The sessions/ dir doesn't exist yet — first run needs to create session

2. Run: cd /home/ubuntu/confessit-scraper && venv/bin/python scrape.py --limit 100
   - Should scrape, parse, and store messages
   - Verify DB has data: venv/bin/python -c "from src.storage.db import init_db, get_messages; init_db(); msgs = get_messages(); print(len(msgs), 'messages')"

3. Run: venv/bin/python report.py
   - Should generate a daily report for yesterday
   - Verify it includes AI Vibe Check and Top Posts sections

4. (Optional) Backfill existing messages after a full scrape

KEY FILES
---------
- scrape.py — CLI entry point for scraping
- report.py — CLI entry point for report generation
- src/scraper/telegram_scraper.py — telethon async scraper (LINE 68 is the auth)
- src/storage/db.py — SQLite layer with v2 migration
- src/parsing/parser.py — structured confession parser
- src/analysis/llm_summarizer.py — OpenAI summarizer
- src/reporting/report.py — Jinja2 report generator
- reports/template.html — NUS-branded HTML template
- .env — credentials (all set)

IMPORTANT
---------
- Use the venv: /home/ubuntu/confessit-scraper/venv/bin/python
- The sessions/ dir will be created on first successful auth
- .env is already configured, don't modify it
- Project root is /home/ubuntu/confessit-scraper
