# NUSConfessIT — ML-Ready Virality Dataset

**72,279 anonymous confessions** from NUSConfessIT (Telegram), scraped from
Feb 2024 to May 2026. Each post is labeled with a virality score and binary
viral flag, ready for supervised learning.

## Quick Stats

| | |
|---|---|
| Posts | 72,279 |
| Date range | 2024-02-26 → 2026-05-24 |
| Total reactions | ~513K |
| Total forwards | ~610K |
| Data points per post | 16 columns |
| File size | ~20 MB (CSV) |
| License | CC BY-NC 4.0 |

## Column Reference

### Raw Data

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Unique post ID (NUSConfessIT internal) |
| `date` | str | ISO 8601 timestamp |
| `confession_text` | str | Full confession body, boilerplate stripped |
| `category` | str | Topic tag extracted from `#Category` (e.g. `studies`, `romance`, `rant`, `campus`, `others`) |

### Metadata Features

| Column | Type | Range | Description |
|--------|------|-------|-------------|
| `hour` | int | 0–23 | Hour of posting |
| `day_of_week` | int | 0–6 | 0=Monday, 6=Sunday |
| `month` | int | 1–12 | Month of posting |
| `is_night` | bool | 0/1 | 1 if hour < 6 or hour ≥ 22 |
| `is_weekend` | bool | 0/1 | 1 if day_of_week ≥ 5 |
| `word_count` | int | 1+ | Whitespace-separated tokens |
| `char_count` | int | 1+ | Total characters |

### Engagement Signals

| Column | Type | Description |
|--------|------|-------------|
| `reactions_count` | int | Telegram reactions (👍 ❤️ 😭 etc.) |
| `reply_count` | int | Public replies in the discussion group |
| `forwards` | int | Times the post was forwarded/shared |

### Targets

| Column | Type | Description |
|--------|------|-------------|
| `virality_score` | float | Weighted composite: `(reactions×1 + replies×2 + forwards×3) / 6` |
| `viral` | bool | 1 if `virality_score` ≥ 75th percentile (threshold: 4.67) |

**Why the composite score?** Forwards (3×) indicate active sharing — the
strongest virality signal. Replies (2×) show discussion engagement. Reactions
(1×) are passive and easy to give. The weights reflect signal quality, and
dividing by 6 keeps the score on a similar scale to raw reactions.

## Source & Collection

Posts are scraped from [@NUSConfessIT](https://t.me/NUSConfessIT) on Telegram
— an anonymous confession channel for the National University of Singapore
community. Each post is a text confession submitted by anonymous users. The
channel runs a voting system via Telegram reactions.

**No filtering has been applied.** This dataset includes every post with
extractable text — short posts, emoji-only posts, low-quality content, and
sensitive topics (including the Helix House incident). Use with appropriate
content warnings.

## Suggested Use Cases

1. **Regression** — predict `virality_score` from text + metadata
2. **Classification** — predict `viral` label (binary: viral vs not)
3. **NLP** — topic modeling, sentiment analysis, text generation fine-tuning
4. **Social science** — study what drives engagement in anonymous online
   communities

## Baseline Results (v6 Model)

The **v6 model** (LightGBM, 5-fold CV) achieved:

| Model | AUC | F1 | Precision | Recall |
|-------|-----|----|-----------|--------|
| TF-IDF + meta (v4 baseline) | 0.774 | 0.545 | 0.447 | 0.697 |
| Emb + meta (default params) | 0.783 | 0.561 | 0.459 | 0.720 |
| **Emb + TF-IDF + meta (tuned)** | **0.804** | **0.575** | **0.473** | **0.733** |

**Best hyperparameters (RandomizedSearchCV, 30 iterations):**

```python
{
    "colsample_bytree": 0.6,
    "learning_rate": 0.05,
    "max_depth": 10,
    "min_child_samples": 20,
    "n_estimators": 300,
    "reg_alpha": 0.5,
    "reg_lambda": 0.1,
    "subsample": 0.6,
}
```

**Feature space used:** 8k-dim TF-IDF (bigrams) + 512-dim sentence embeddings
+ 7 metadata features + 17 one-hot categories ≈ 8,536 total dimensions.

## Quick Start

```python
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
import lightgbm as lgb

df = pd.read_csv("confessit_v6_dataset.csv")

# Text → TF-IDF
tfidf = TfidfVectorizer(ngram_range=(1,2), max_features=8000,
                        sublinear_tf=True, min_df=3, max_df=0.85)
X_tfidf = tfidf.fit_transform(df["confession_text"])

# Metadata
meta = df[["hour", "day_of_week", "month", "is_night",
           "is_weekend", "word_count", "char_count"]].values
cats = pd.get_dummies(df["category"])

# Combine
from scipy.sparse import hstack, csr_matrix
X = hstack([X_tfidf, csr_matrix(meta), csr_matrix(cats.values)])

y = df["viral"].values
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

clf = lgb.LGBMClassifier(
    n_estimators=300, max_depth=10, learning_rate=0.05,
    subsample=0.6, colsample_bytree=0.6,
    min_child_samples=20, reg_lambda=0.1, reg_alpha=0.5,
    class_weight="balanced", random_state=42, verbose=-1
)
clf.fit(X_train, y_train)
```

## Companion Files

| File | Description |
|------|-------------|
| `confessit_v6_dataset.csv` | Main dataset (this README) |
| `embeddings_v5.npy` | Precomputed 512-dim sentence embeddings (row-aligned) |
| `embedding_ids_v5.npy` | Post IDs mapping embeddings to rows in this CSV |

To load embeddings aligned to this CSV:

```python
import numpy as np
embeddings = np.load("embeddings_v5.npy")     # (72279, 512)
embed_ids = np.load("embedding_ids_v5.npy")   # (72279,)
# embed_ids[i] == df["id"].iloc[i] — row-aligned
```

## Content Warning

This dataset contains unmoderated anonymous posts. Some content may include
discussions of suicide, self-harm, mental health struggles, relationship
issues, and other sensitive topics. Handle with appropriate care and ethics
review.