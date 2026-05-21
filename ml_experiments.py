#!/usr/bin/env python3
"""
ML experiments: predict reaction count class from confession post text + metadata.

Target: reactions_count binned into 3 classes
  - low    (0-2)   ~50th percentile
  - medium (3-9)   ~75th-90th percentile
  - high   (10+)   top tier

Steps:
  1. Export CSV with features
  2. Feature engineering (TF-IDF + metadata + sentiment + text stats)
  3. Train 7 classifiers with cross-validation
  4. Report F1 scores, pick best model
"""

import sqlite3
import re
import csv
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB, ComplementNB
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.svm import LinearSVC
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report, f1_score
import xgboost as xgb
import lightgbm as lgb

warnings.filterwarnings("ignore")

DB_PATH = Path(__file__).parent / "data" / "messages.db"
CSV_OUT = Path(__file__).parent / "data" / "confessions_ml.csv"

# ─── Template cleaning (same as export_training_data.py) ──────────────────────

_TEMPLATE_MARKERS = [
    "Click here", "NUSConfessIT_bot",
    "👇 Comment **below** anonymously",
    "😆 Send an **anonymous message**",
    "Send an **anonymous message**",
    "PM THIS", "PM Confessor",
    "post a confession", "post **YOUR OWN** confession",
    "post your own anonymous",
]

def _is_template_line(line: str) -> bool:
    s = line.strip()
    return bool(s) and any(m in s for m in _TEMPLATE_MARKERS)

def clean_body(text: str) -> str | None:
    if not text:
        return None
    lines = text.strip().split("\n")
    for i, line in enumerate(lines):
        if _is_template_line(line):
            if i == 0:
                return None
            body = "\n".join(lines[:i]).strip()
            return body or None
    return text.strip()

def extract_confession_text(raw: str) -> str | None:
    """Pull just the confession body from the structured Telegram post."""
    if not raw:
        return None
    # Try to find content between --- markers
    match = re.search(r"---\s*\n(.*?)\n---", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return clean_body(raw)

# ─── Label binning ────────────────────────────────────────────────────────────

def bin_reactions(n: int) -> str:
    if n <= 2:
        return "low"
    elif n <= 9:
        return "medium"
    else:
        return "high"

# ─── Feature helpers ──────────────────────────────────────────────────────────

def parse_category(text: str) -> str:
    """Extract category tag like #Campus, #Studies etc."""
    if not text:
        return "unknown"
    m = re.search(r"\*\*#(\w+)\*\*", text)
    return m.group(1).lower() if m else "unknown"

def extract_hour(date_str: str) -> int:
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.hour
    except Exception:
        return -1

def extract_dow(date_str: str) -> int:
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.weekday()  # 0=Mon
    except Exception:
        return -1

# ─── Step 1: Export CSV ───────────────────────────────────────────────────────

def export_csv():
    print("=" * 60)
    print("STEP 1: Exporting CSV from SQLite")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT
            id,
            channel,
            date,
            COALESCE(NULLIF(content,''), NULLIF(text,'')) AS raw_body,
            text,
            views,
            forwards,
            reactions_count,
            reply_count,
            word_count,
            char_count
        FROM messages
        WHERE is_reply = 0
          AND COALESCE(NULLIF(content,''), NULLIF(text,'')) IS NOT NULL
        ORDER BY date DESC
    """).fetchall()
    conn.close()

    sia = SentimentIntensityAnalyzer()
    records = []

    for (post_id, channel, date, raw_body, raw_text, views, forwards,
         reactions, reply_count, word_count, char_count) in rows:

        confession = extract_confession_text(raw_body)
        if not confession or len(confession) < 10:
            continue

        alpha_ratio = sum(c.isalpha() for c in confession) / max(len(confession), 1)
        if alpha_ratio < 0.2:
            continue

        sent = sia.polarity_scores(confession)
        category = parse_category(raw_text or raw_body)
        hour = extract_hour(date)
        dow = extract_dow(date)

        has_question = int("?" in confession)
        exclamation_count = confession.count("!")
        caps_ratio = sum(c.isupper() for c in confession) / max(len(confession), 1)
        emoji_count = sum(1 for c in confession if ord(c) > 0x1F300)
        avg_word_len = (
            sum(len(w) for w in confession.split()) / max(len(confession.split()), 1)
        )

        records.append({
            "post_id": post_id,
            "channel": channel,
            "date": date,
            "confession_text": confession,
            "category": category,
            "hour": hour,
            "day_of_week": dow,
            "views": views or 0,
            "forwards": forwards or 0,
            "word_count": len(confession.split()),
            "char_count": len(confession),
            "avg_word_len": round(avg_word_len, 3),
            "has_question": has_question,
            "exclamation_count": exclamation_count,
            "caps_ratio": round(caps_ratio, 4),
            "emoji_count": emoji_count,
            "sentiment_pos": round(sent["pos"], 4),
            "sentiment_neg": round(sent["neg"], 4),
            "sentiment_neu": round(sent["neu"], 4),
            "sentiment_compound": round(sent["compound"], 4),
            "reactions_count": reactions or 0,
            "reply_count": reply_count or 0,
            "reaction_label": bin_reactions(reactions or 0),
        })

    df = pd.DataFrame(records)
    df.to_csv(CSV_OUT, index=False, quoting=csv.QUOTE_NONNUMERIC)
    print(f"Exported {len(df)} rows → {CSV_OUT}")
    print(f"Label distribution:\n{df['reaction_label'].value_counts().to_string()}")
    print()
    return df

# ─── Step 2: Feature transformer ──────────────────────────────────────────────

class MetaFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extract numeric metadata features from a DataFrame."""

    META_COLS = [
        "hour", "day_of_week", "word_count", "char_count", "avg_word_len",
        "has_question", "exclamation_count", "caps_ratio", "emoji_count",
        "sentiment_pos", "sentiment_neg", "sentiment_neu", "sentiment_compound",
    ]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X[self.META_COLS].values.astype(float)


class CategoryEncoder(BaseEstimator, TransformerMixin):
    """One-hot encode category."""

    def fit(self, X, y=None):
        self.cats_ = sorted(X["category"].unique())
        return self

    def transform(self, X):
        arr = np.zeros((len(X), len(self.cats_)), dtype=float)
        for i, cat in enumerate(X["category"]):
            if cat in self.cats_:
                arr[i, self.cats_.index(cat)] = 1.0
        return arr


class TextSelector(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X["confession_text"].fillna("").values


# ─── Step 3: ML Experiments ───────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent / "data" / "ml_results"
SUMMARY_CSV = RESULTS_DIR / "summary.csv"

TFIDF_KWARGS = dict(ngram_range=(1, 1), max_features=3000, sublinear_tf=True, min_df=3)
LABEL_ORDER = ["low", "medium", "high"]


def make_feature_pipeline(clf, scale_meta=False):
    steps = [
        ("features", FeatureUnion([
            ("tfidf", Pipeline([("sel", TextSelector()),
                                ("tfidf", TfidfVectorizer(**TFIDF_KWARGS))])),
            ("meta", MetaFeatureExtractor()),
            ("cat", CategoryEncoder()),
        ])),
    ]
    if scale_meta:
        steps.append(("scaler", StandardScaler(with_mean=False)))
    steps.append(("clf", clf))
    return Pipeline(steps)


def get_models():
    return {
        "logistic_regression": make_feature_pipeline(
            LogisticRegression(max_iter=500, C=1.0, solver="lbfgs"), scale_meta=True
        ),
        "complement_naive_bayes": Pipeline([
            ("sel", TextSelector()),
            ("tfidf", TfidfVectorizer(**TFIDF_KWARGS)),
            ("clf", ComplementNB(alpha=0.1)),
        ]),
        "linear_svm": make_feature_pipeline(
            LinearSVC(max_iter=1000, C=0.5), scale_meta=True
        ),
        "random_forest": make_feature_pipeline(
            RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
        ),
        "gradient_boosting": make_feature_pipeline(
            GradientBoostingClassifier(n_estimators=80, max_depth=3, learning_rate=0.15,
                                        random_state=42, subsample=0.8)
        ),
        "xgboost": make_feature_pipeline(
            xgb.XGBClassifier(n_estimators=80, max_depth=4, learning_rate=0.15,
                               eval_metric="mlogloss", random_state=42, n_jobs=-1)
        ),
        "lightgbm": make_feature_pipeline(
            lgb.LGBMClassifier(n_estimators=80, max_depth=4, learning_rate=0.15,
                                random_state=42, n_jobs=-1, verbose=-1)
        ),
        "mlp_neural_net": make_feature_pipeline(
            MLPClassifier(hidden_layer_sizes=(128,), max_iter=200, random_state=42,
                           early_stopping=True, validation_fraction=0.1,
                           learning_rate_init=0.001), scale_meta=True
        ),
    }


def run_one_model(name: str, pipeline, df: pd.DataFrame, y: np.ndarray,
                  cv: StratifiedKFold) -> dict:
    """Run CV for one model, write results to its own file, return summary dict."""
    from sklearn.model_selection import train_test_split

    out_path = RESULTS_DIR / f"{name}.txt"
    print(f"  Running {name}...", flush=True)

    f1_macro_scores = cross_val_score(pipeline, df, y, cv=cv, scoring="f1_macro", n_jobs=1)
    f1_weighted_scores = cross_val_score(pipeline, df, y, cv=cv, scoring="f1_weighted", n_jobs=1)

    mean_macro = f1_macro_scores.mean()
    std_macro = f1_macro_scores.std()
    mean_weighted = f1_weighted_scores.mean()

    # Per-class breakdown on a held-out 20%
    X_train, X_test, y_train, y_test = train_test_split(
        df, y, test_size=0.2, stratify=y, random_state=42
    )
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred, target_names=LABEL_ORDER)

    result = {
        "model": name,
        "f1_macro_mean": round(mean_macro, 4),
        "f1_macro_std": round(std_macro, 4),
        "f1_weighted_mean": round(mean_weighted, 4),
    }

    with open(out_path, "w") as f:
        f.write(f"Model: {name}\n")
        f.write(f"CV F1-macro : {mean_macro:.4f} ± {std_macro:.4f}\n")
        f.write(f"CV F1-weighted: {mean_weighted:.4f}\n")
        f.write(f"CV fold scores: {np.round(f1_macro_scores, 4).tolist()}\n\n")
        f.write("Classification report (80/20 hold-out):\n")
        f.write(report)

    # Append one row to the running summary CSV
    summary_exists = SUMMARY_CSV.exists()
    with open(SUMMARY_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        if not summary_exists:
            writer.writeheader()
        writer.writerow(result)

    print(f"  {name:<28} F1-macro={mean_macro:.4f} ± {std_macro:.4f}  "
          f"F1-weighted={mean_weighted:.4f}  → {out_path.name}", flush=True)
    return result


def run_experiments(df: pd.DataFrame):
    print("=" * 60)
    print("STEP 2: ML Experiments")
    print("=" * 60)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_CSV.unlink(missing_ok=True)  # fresh run

    y = np.array([LABEL_ORDER.index(l) for l in df["reaction_label"]])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    print(f"\nResults will be written to {RESULTS_DIR}/\n")

    results = []
    for name, pipeline in get_models().items():
        try:
            result = run_one_model(name, pipeline, df, y, cv)
            results.append(result)
        except Exception as e:
            print(f"  ERROR in {name}: {e}", flush=True)

    results_df = pd.DataFrame(results).sort_values("f1_macro_mean", ascending=False)

    print()
    print("=" * 60)
    print("RESULTS SUMMARY (ranked by CV F1-macro)")
    print("=" * 60)
    print(results_df.to_string(index=False))

    best = results_df.iloc[0]
    return results_df, best["model"]


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = export_csv()
    results_df, best_name = run_experiments(df)

    print()
    print("=" * 60)
    print(f"WINNER: {best_name}")
    print(f"  F1-macro : {results_df.iloc[0]['f1_macro_mean']:.4f} "
          f"± {results_df.iloc[0]['f1_macro_std']:.4f}")
    print(f"  F1-weighted: {results_df.iloc[0]['f1_weighted_mean']:.4f}")
    print(f"\nPer-model reports in: {RESULTS_DIR}/")
    print(f"Summary CSV: {SUMMARY_CSV}")
    print("=" * 60)
    print("=" * 60)
