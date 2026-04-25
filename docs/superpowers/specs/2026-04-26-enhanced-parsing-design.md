# NUSConfessIT Enhanced Parsing & Analysis — Design

**Date**: 2026-04-26
**Status**: Draft — awaiting user review

## Goal

Add structured parsing of confession format, engagement rankings, and LLM-powered daily summaries.

## Background

The NUSConfessIT Telegram channel posts confessions in a structured format that the current scraper doesn't parse:

```
**[Category] [Emoji]: [Title]**

**ID:** #[ID]
---
[Content]
---
```

Example:
```
**#Studies** 📚: __WORRIED ABOUT GETTING A CU FOR CFG1002 🤯__

**ID:** #CBS854MC
---
Does it matter if you get a CU for cfg1002?? Freaking out rn
---
```

Current state:
- Raw text stored as single `text` field
- Already capturing: views, forwards, reactions_count, reply_count, date
- No category/title/content extraction
- VADER sentiment + topic classification exists

## Requirements

### 1. Structured Parsing

Extract fields from each confession:

| Field | Source | Example |
|-------|--------|---------|
| `category` | Before first `**` | "Studies" |
| `confession_id` | After `#` in "ID:" line | "CBS854MC" |
| `title` | After `:` in header line | "WORRIED ABOUT GETTING A CU FOR CFG1002" |
| `content` | Between `---` separators | "Does it matter if you get a CU..." |
| `raw_text` | Keep existing full text | (unchanged) |

### 2. Top Posts Ranking

New section in daily HTML report:

- **Top 5 by Reactions**: Posts with highest `reactions_count`
- Show: rank, category, title snippet (50 chars), reaction count
- Link to confession ID

### 3. LLM Summary

Add daily summary to report header:

- **3-5 bullet points** from OpenAI API
- Theme/topic summary: "Internships are on people's mind..."
- Input: all day's confession content concatenated
- Fallback: if API fails, show "LLM summary unavailable"

## Architecture

```
scrape.py → telegram_scraper.py
              ↓
         src/parsing/parser.py   ← NEW
              ↓
         src/storage/db.py      ← add columns
              ↓
report.py → analyze → llm_summarizer.py  ← NEW (OpenAI)
              ↓
         visualizations.py → new chart
              ↓
         report.html
```

### New Files

- `src/parsing/__init__.py`
- `src/parsing/parser.py` — regex-based extraction
- `src/analysis/llm_summarizer.py` — OpenAI client

### Modified Files

- `src/storage/db.py` — ALTER TABLE add columns
- `src/analysis/visualizations.py` — add top posts chart
- `src/reporting/report.py` — include LLM summary

### Database Schema Change

```sql
ALTER TABLE messages ADD COLUMN category TEXT;
ALTER TABLE messages ADD COLUMN confession_id TEXT;
ALTER TABLE messages ADD COLUMN title TEXT;
ALTER TABLE messages ADD COLUMN content TEXT;
```

### Environment Variables

```
OPENAI_API_KEY=sk-...  # User provides
```

## Implementation Steps

### Step 1: Database Migration
- Add 4 new columns to messages table
- Parse existing messages, backfill

### Step 2: Parser
- Write regex patterns for extraction
- Handle edge cases (missing fields, malformed)
- Unit tests with sample confessions

### Step 3: Scrape Integration
- Run parser on new messages during scrape
- Store extracted fields

### Step 4: LLM Summarizer
- OpenAI client wrapper
- Chunk content if > 8K tokens
- Cache summaries to avoid re-fetching

### Step 5: Report Updates
- Add "Top Posts by Reactions" section
- Add LLM summary to header
- New chart type

## Edge Cases

- Missing ID: use NULL, log warning
- Missing content: fall back to full text
- Malformed format: log, continue, don't crash
- LLM API failure: show fallback message
- Empty day: show "No confessions" state

## Open Questions

- [x] Confession ID format: Yes, always uppercase alphanumeric 6 chars (e.g., CFR497VY)
- [x] Title extraction: Strip emojis, markdown `__` formatting
- [x] LLM model: GPT-4o mini (fast, cheap, sufficient for summary)

## Acceptance Criteria

- [ ] Existing messages parsed with 90%+ success rate
- [ ] New messages parsed during scrape
- [ ] Top 5 shows in daily report
- [ ] LLM summary appears in report header
- [ ] Graceful fallbacks on failure
- [ ] No data loss from migration