# confessit-scraper

Scraper, dashboard, ML experiments, and public viewer for [@NUSConfessIT](https://t.me/NUSConfessIT) — an anonymous confession channel for the NUS community on Telegram.

**Live site →** [confessit.space](https://confessit.space)
**Analysis writeup →** [anselmlong.com/blog/nus-confessit-analysis](https://anselmlong.com/blog/nus-confessit-analysis)

---

## What's in here

| Component | Description |
|-----------|-------------|
| `scrape.py` | Incremental Telegram scraper (Telethon) |
| `scrape_replies.py` | Fetches reply counts from the discussion group |
| `refresh_reactions.py` | Refreshes reaction counts on existing posts |
| `server.py` | Local Flask dashboard — top posts, search, individual post pages |
| `frontend/` | Next.js 15 public site deployed to confessit.space |
| `ml/` | Virality prediction experiments (TF-IDF, embeddings, LightGBM) |
| `export_v6_dataset.py` | Exports the ML-ready CSV dataset |
| `report.py` | Generates HTML digest reports |
| `dataset/` | Published dataset (72,279 posts, CC BY-NC 4.0) |

Data is stored locally in `data/messages.db` (SQLite).

---

## Setup

**Python scraper + local server**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your Telegram API credentials
```

Get API credentials at [my.telegram.org](https://my.telegram.org).

**Next.js frontend**

```bash
cd frontend
npm install
npm run dev
```

---

## Scraper

```bash
python scrape.py                    # incremental fetch (new messages only)
python scrape.py --limit 500        # fetch at most 500 new messages
python scrape.py --since-id 0       # re-fetch everything from the beginning
python scrape_replies.py            # update reply counts
python refresh_reactions.py         # refresh reaction counts
```

The scraper writes to `data/messages.db`. First run triggers a Telegram auth flow — a session file is saved to `sessions/` so subsequent runs are silent.

---

## Local dashboard

```bash
python server.py           # runs at http://localhost:5000
python server.py --port 8080
```

Routes: `/` (top posts), `/search`, `/post/<id>`, `/stats`.

---

## Dataset

`dataset/confessit_v6_dataset.csv` — 72,279 posts with virality scores, binary viral labels, and metadata features. See `dataset/README.md` for the full schema and baseline ML results.

To export a fresh dataset from the local DB:

```bash
python export_v6_dataset.py
```

---

## ML experiments

Scripts in `ml/` cover the full modelling pipeline:

| Script | What it does |
|--------|-------------|
| `ml_embeddings.py` | Computes sentence embeddings via sentence-transformers |
| `ml_viral_classifier.py` | Baseline TF-IDF + metadata classifier |
| `ml_viral_v4.py` / `ml_viral_v5.py` | Iterative model improvements |
| `ml_v6_combined.py` | Best model: TF-IDF + embeddings + metadata (AUC 0.804) |
| `ml_ablation.py` | Feature ablation study |
| `ml_feature_importance.py` | SHAP feature importance |
| `ml_landscape.py` / `ml_cluster_explore.py` | Embedding visualisation and clustering |
| `ml_experiments.py` / `ml_experiments_v2*.py` | Hyperparameter search |

Fine-tuning experiments (LLM on confession text) live in `finetune_confessit.py` and `unsloth-finetune.ipynb`. SLURM job scripts are in `ml/slurm_finetune.sh` and `ml/infer-slurm.sh`.

---

## Content warning

The dataset and database contain unmoderated anonymous posts, including discussions of suicide, self-harm, mental health, and other sensitive topics.
