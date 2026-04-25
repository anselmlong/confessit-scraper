HANDOFF CONTEXT
===============

USER REQUESTS (AS-IS)
---------------------
- "can you render the html file as a local host instead of showing it to the user as just a html file?"
- "INTEGRATE THIS SERVER INTO THE REPORT.PY COMMAND"
- "i want better parsing of the confessions, and better analysis also. perhaps run through a LLM to summarise as well? i want a way to do something with the data, perhaps even fine tuning an LLM in the future..."
- "A" (chose Option A - integrated roadmap for parsing → analysis → LLM summarization → fine-tuning prep)
- "yeah lets do option 1 first" (structured parsing, top posts ranking, LLM summary)
- "instead of returning a html file, we can just create a web app that displays it?"
- "dashboard. let's just do fastapi, next.js standard stuff. use /impeccable to design"
- "show me visual? but actually maybe a more fun direction would be great too"
- User provided OpenAI API key (stored in ~/.gstack/openai.json for security)

GOAL
----
Build an enhanced NUSConfessIT dashboard web app (FastAPI + Next.js) with structured confession parsing, top posts ranking by reactions, LLM-powered summaries, and a fun campus-vibe design.

WORK COMPLETED
--------------
- Added local HTTP server to report.py with --serve and --open flags
- Created design spec: docs/superpowers/specs/2026-04-26-enhanced-parsing-design.md
- Explored existing codebase structure (scraper, storage, analysis, reporting modules)
- Researched dashboard design trends for 2025
- Proposed fun design directions: Campus Feed (Instagram-style), NUS Radio, Confession Booth
- Saved OpenAI API key securely to ~/.gstack/openai.json

CURRENT STATE
-------------
- API key needs organization verification on OpenAI before AI design generation works
- Design exploration was interrupted - no visual mockups generated yet
- Existing codebase: Python scraper → SQLite → daily HTML reports

PENDING TASKS
-------------
1. Complete design exploration - generate/choose visual mockup direction
2. Update design spec to reflect web app (FastAPI + Next.js) instead of HTML reports
3. Set up Next.js + FastAPI project structure
4. Implement structured parsing (category, confession_id, title, content)
5. Add database migration for new columns
6. Build LLM summarizer with OpenAI
7. Create top posts by reactions ranking
8. Build dashboard UI with chosen design direction

KEY FILES
---------
- report.py - CLI for generating reports, now has --serve and --open flags
- docs/superpowers/specs/2026-04-26-enhanced-parsing-design.md - current design spec
- src/storage/db.py - SQLite database layer
- src/analysis/sentiment.py - VADER sentiment + topic classification
- src/analysis/visualizations.py - Chart generation
- src/reporting/report.py - Jinja2 HTML report generation
- data/messages.db - SQLite database with ~40K messages
- reports/template.html - Jinja2 template for HTML reports

IMPORTANT DECISIONS
-------------------
- Option 1 chosen: Incremental upgrade (parsing + ranking + LLM summary, defer fine-tuning)
- Chose FastAPI + Next.js for web app
- Design direction: fun/campus-y, not enterprise/corporate
- NUS brand colors: #003D7C (blue), #EF7C00 (orange)
- LLM model: GPT-4o mini for summarization

EXPLICIT CONSTRAINTS
--------------------
- Must use brainstorming skill before implementation (HARD-GATE)
- Design must be fun/campus-y, not corporate
- OpenAI API key provided by user (stored in ~/.gstack/openai.json)

CONTEXT FOR CONTINUATION
------------------------
- Need to wait for OpenAI organization verification OR build manual HTML preview instead of AI-generated mockups
- Design spec needs updating to reflect web app architecture (FastAPI + Next.js) vs static HTML reports
- Next step: Either complete design exploration or move to implementation planning with writing-plans skill
- User approved Option 1 design, but pivot to web app changes scope significantly

---

TO CONTINUE IN A NEW SESSION:

1. Press 'n' in OpenCode TUI to open a new session, or run 'opencode' in a new terminal
2. Paste the HANDOFF CONTEXT above as your first message
3. Add your request: "Continue from the handoff context above. [Your next task]"