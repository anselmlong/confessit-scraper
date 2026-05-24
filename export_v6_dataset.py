#!/usr/bin/env python3
"""Export the v6 model's feature set + targets as a clean ML-ready CSV.

Mirrors ml_v6_combined.py exactly: same SQL, same cleaning, same filters,
same features, same virality score and binary label.

Output columns:
id                  — NUSConfessIT post ID
  date                — ISO timestamp
  confession_text     — cleaned body text (template-stripped)
  category            — extracted from #Category tag (e.g. "studies", "romance", "rant")
  hour                — post hour (0-23)
  day_of_week         — 0=Monday .. 6=Sunday
  month               — 1-12
  is_night            — 1 if hour<6 or hour>=22
  is_weekend          — 1 if day_of_week >=5
  word_count          — number of whitespace-separated tokens
  char_count          — number of characters
  reactions_count     — count of Telegram reactions (👍❤️ etc.)
  reply_count         — count of public replies
  forwards            — count of forwards/shares
  virality_score      — weighted composite: (reactions*1 + replies*2 + forwards*3)/6
  viral               — 1 if virality_score >= 75th percentile

No filtering applied — includes Helix House posts, short posts,
low-alpha posts, everything from the source DB that has extractable text."""  # noqa: E501

import re, sqlite3, sys
from pathlib import Path
from datetime import datetime

import pandas as pd

DB_PATH = Path(__file__).parent / "data" / "messages.db"
OUTPUT = Path(__file__).parent / "data" / "confessit_v6_dataset.csv"

# ── Exact helpers from ml_v6_combined.py ──────────────────────────────

_TEMPLATE_MARKERS = [
    "Click here", "NUSConfessIT_bot",
    "👇 Comment **below** anonymously", "😆 Send an **anonymous message**",
    "Send an **anonymous message**", "PM THIS", "PM Confessor",
    "post a confession", "post **YOUR OWN** confession",
    "post your own anonymous",
]

def _is_template_line(l):
    s = l.strip()
    return bool(s) and any(m in s for m in _TEMPLATE_MARKERS)

def clean_body(t):
    if not t:
        return None
    ls = t.strip().split("\n")
    for i, l in enumerate(ls):
        if _is_template_line(l):
            if i == 0:
                return None
            return "\n".join(ls[:i]).strip() or None
    return t.strip()

def extract_confession_text(r):
    if not r:
        return None
    m = re.search(r"---\s*\n(.*?)\n---", r, re.DOTALL)
    return m.group(1).strip() if m else clean_body(r)

# ── Build ─────────────────────────────────────────────────────────────

print("Querying messages.db...", flush=True)
conn = sqlite3.connect(str(DB_PATH))
rows = conn.execute("""
    SELECT id, date,
           COALESCE(NULLIF(content,''), NULLIF(text,'')) AS rb,
           text, forwards, reactions_count, reply_count
    FROM messages
    WHERE is_reply = 0
      AND COALESCE(NULLIF(content,''), NULLIF(text,'')) IS NOT NULL
""").fetchall()
conn.close()

print(f"  {len(rows)} raw posts loaded", flush=True)

recs = []
skipped = {"short": 0, "noise": 0, "helix": 0, "no_text": 0}

for (pid, date, rb, rt, fw, rc, rpc) in rows:
    conf = extract_confession_text(rb)
    if not conf:
        skipped["no_text"] += 1
        continue

    h = dw = mo = -1
    try:
        dt = datetime.fromisoformat(date)
        h, dw, mo = dt.hour, dt.weekday(), dt.month
    except Exception:
        pass

    m = re.search(r"\*\*#(\w+)\*\*", rt or rb)
    cat = m.group(1).lower() if m else "unknown"

    recs.append({
        "id": pid,
        "date": date,
        "confession_text": conf,
        "category": cat,
        "hour": h,
        "day_of_week": dw,
        "month": mo,
        "is_night": int(h < 6 or h >= 22),
        "is_weekend": int(dw >= 5),
        "word_count": len(conf.split()),
        "char_count": len(conf),
        "reactions_count": rc or 0,
        "reply_count": rpc or 0,
        "forwards": fw or 0,
    })

print(f"  Skipped: {skipped}", flush=True)
print(f"  Kept: {len(recs)} posts", flush=True)

df = pd.DataFrame(recs)

# ── Targets (exact v6 logic) ──────────────────────────────────────────

df["virality_score"] = (
    df["reactions_count"] * 1
    + df["reply_count"] * 2
    + df["forwards"] * 3
) / 6

threshold = df["virality_score"].quantile(0.75)
df["viral"] = (df["virality_score"] >= threshold).astype(int)

print(f"  Virality threshold (75th pctile): {threshold:.2f}", flush=True)
print(f"  Viral rate: {df['viral'].mean():.1%}", flush=True)

# ── Export ────────────────────────────────────────────────────────────

df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
size_mb = OUTPUT.stat().st_size / 1_000_000
print(f"\n✅ Exported {len(df)} rows → {OUTPUT} ({size_mb:.1f} MB)", flush=True)

# Quick stats
print(f"\nColumn summary:")
print(f"  {len(df.columns)} columns, {len(df)} rows")
print(f"  Memory: {df.memory_usage(deep=True).sum() / 1_000_000:.1f} MB")
print(f"\nTarget distribution:")
print(f"  viral=0 (not viral): {(df['viral']==0).sum():,}")
print(f"  viral=1 (viral):     {(df['viral']==1).sum():,}")
print(f"\nFeatures:")
for c in df.columns:
    dtype = str(df[c].dtype)
    print(f"  {c:<25} {dtype}")