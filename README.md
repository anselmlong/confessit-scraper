# NUSConfessIT Scraper + Dashboard + Fine-Tuning

Scrapes the [NUSConfessIT Telegram channel](https://t.me/NUSConfessIT), stores messages in SQLite, runs sentiment analysis and NUS-specific topic classification, generates self-contained daily HTML reports, provides a live web dashboard, and fine-tunes LLMs on confession data.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What It Does

1. **Scrapes** messages from `t.me/NUSConfessIT` using the Telegram API (incremental — only fetches new messages on repeat runs)
2. **Stores** them in a local SQLite database (`data/messages.db`)
3. **Analyses** each message:
   - Sentiment score (positive / neutral / negative) via VADER
   - Topic classification into 6 NUS-specific buckets
   - Word frequency and engagement metrics
4. **Generates** a daily HTML report with charts
5. **Serves** a live web dashboard with browsing, search, and per-post detail views
6. **Fine-tunes** Qwen 2.5 7B on confession-style posts via QLoRA (Unsloth)

---

## Report Preview

Each daily report (`reports/YYYY-MM-DD_digest.html`) contains:

| Section | Description |
|---|---|
| **TL;DR** | 3–5 heuristic-generated bullets summarising the day |
| **By the Numbers** | Total confessions, avg length, engagement stats |
| **Mood-o-meter** | 😊 positive% / 😐 neutral% / 😢 negative% |
| **Hot Topics** | Ranked topic buckets with sample messages |
| **Word of the Day** | Top 10 most-used words |
| **Highlights** | 3 most positive + 3 most negative confessions |
| **Hourly Heatmap** | Posting activity by hour of day |

Charts (sentiment pie, hourly bar, topic bar, word cloud) are embedded as base64 PNGs — the report is a single portable HTML file.

---

## Topic Classification

Messages are classified into these NUS-specific buckets (a message can belong to multiple):

| Topic | Keywords include |
|---|---|
| **Academics** | exam, grade, module, gpa, cap, prof, deadline… |
| **Social** | friend, crush, relationship, cca, club, party… |
| **Mental Health** | stress, anxiety, burnout, overwhelmed, lonely… |
| **Accommodation** | hall, hostel, utown, pgp, residential college… |
| **Career** | internship, interview, resume, linkedin, OA… |
| **Food** | canteen, deck, makan, lunch, hungry… |

---

## Setup

### 1. Prerequisites

- Python 3.10+
- A Telegram account

### 2. Get Telegram API Credentials

1. Go to [my.telegram.org](https://my.telegram.org) and log in
2. Click **API development tools**
3. Create a new application (any name works)
4. Copy the **API ID** and **API Hash**

> These credentials are free and tied to your Telegram account. Keep them private.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+651****5678
```

> On first run, Telethon will send a login code to your Telegram app. Enter it when prompted. The session is saved to `sessions/` so you only need to do this once.

---

## Usage

### Scrape Messages

```bash
# Incremental (only fetches messages newer than what's in the DB)
python scrape.py

# Full fetch (up to N messages)
python scrape.py --limit 5000

# Different channel
python scrape.py --channel https://t.me/someotherchannel

# Start from a specific message ID
python scrape.py --since-id 12345
```

### Generate a Report

```bash
# Yesterday's report (default)
python report.py

# Specific date
python report.py --date 2025-04-20

# Skip chart generation (faster, text-only report)
python report.py --no-charts
```

Reports are saved to `reports/YYYY-MM-DD_digest.html`.

### Web Dashboard

A live Flask dashboard for browsing, searching, and exploring confessions.

```bash
# Start the dashboard (default port 5000)
python server.py

# Custom port
python server.py --port 8080
```

Open `http://localhost:5000` in your browser.

**Features:**
- Top confessions by reactions, replies, or custom score
- Time range filters (week / month / year / all)
- Full-text search across titles and body text
- Per-post detail page with all inline and discussion-group replies
- Overview stats (total posts, engagement, monthly activity chart)
- Telegram Markdown rendered to HTML

### Fine-Tuning (QLoRA)

Train a confess-style text generator using Unsloth + QLoRA on the scraped data.

```bash
# 1. Export training data from SQLite
python export_training_data.py

# 2. Train on a single GPU
python finetune_confessit.py \
    --data data/confessions.jsonl \
    --output ./outputs \
    --epochs 3 \
    --lr 2e-4 \
    --batch-size 2 \
    --grad-accum 4 \
    --max-seq-length 512 \
    --lora-r 16

# 3. Push to HuggingFace Hub
python finetune_confessit.py \
    --data data/confessions.jsonl \
    --hf-token hf_xxxx \
    --hf-repo your-username/confessit-qwen-2.5-7b-lora
```

**SLURM cluster:** submit via sbatch:

```bash
sbatch slurm_finetune.sh
```

**Colab:** open `unsloth-finetune.ipynb` in Google Colab (T4 free tier works).

---

## Project Structure

```
confessit-scraper/
├── scrape.py                       # CLI: scrape and store messages
├── report.py                       # CLI: generate daily HTML report
├── server.py                       # CLI: web dashboard (Flask)
├── export_training_data.py         # Export SQLite -> causal LM JSONL
├── finetune_confessit.py           # Unsloth QLoRA training script
├── slurm_finetune.sh               # SLURM sbatch wrapper for training
├── unsloth-finetune.ipynb          # Colab-ready fine-tuning notebook
├── requirements.txt
├── .env.example
├── FINETUNE_SETUP.md               # Fine-tuning setup & config reference
│
├── src/
│   ├── scraper/
│   │   └── telegram_scraper.py     # Telethon-based async scraper
│   ├── storage/
│   │   └── db.py                   # SQLite layer (init, save, query)
│   ├── analysis/
│   │   ├── processor.py            # Text cleaning, metadata, word freq
│   │   ├── sentiment.py            # VADER sentiment + topic classifier
│   │   ├── stats.py                # Daily stats, trends, engagement
│   │   └── visualizations.py       # matplotlib/seaborn/wordcloud charts
│   └── reporting/
│       └── report.py               # Jinja2 HTML report generator
│
├── templates/
│   └── index.html                  # Dashboard main page
│   └── post.html                   # Dashboard per-post detail
│
├── reports/
│   └── template.html               # Jinja2 report template (NUS-branded)
│
└── data/
    ├── messages.db                 # SQLite DB (gitignored)
    └── confessions.jsonl           # Exported training data
```

---

## Automating Daily Reports

Use cron to scrape and report automatically:

```cron
# Scrape at 11:55 PM daily, generate report at midnight
55 23 * * * cd /path/to/confessit-scraper && python scrape.py
0  0  * * * cd /path/to/confessit-scraper && python report.py
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `telethon` | Telegram MTProto API client |
| `vaderSentiment` | Rule-based social media sentiment analysis |
| `matplotlib` + `seaborn` | Chart generation |
| `wordcloud` | Word cloud images |
| `Jinja2` | HTML report templating |
| `pandas` | Data manipulation |
| `python-dotenv` | `.env` credential loading |
| `rich` | Pretty CLI output |
| `flask` + `markupsafe` | Web dashboard |
| `unsloth` | QLoRA fine-tuning |
| `transformers` + `datasets` + `trl` + `peft` + `bitsandbytes` | Training stack |

---

## Notes

- This scraper accesses a **public Telegram channel** using the official Telegram API — no scraping of private content.
- The `data/` and `sessions/` directories are gitignored to prevent credential and database leaks.
- VADER sentiment works best for short, informal English text — ideal for confessions but may misread Singlish slang.

---

## License

MIT