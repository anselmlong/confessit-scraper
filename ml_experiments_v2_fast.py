#!/usr/bin/env python3
"""Fast regression experiments — skips slow models, goes straight to results."""

import sys, csv, warnings, re, sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from scipy.stats import boxcox

from sklearn.model_selection import KFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import Ridge, HuberRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import lightgbm as lgb
import xgboost as xgb

warnings.filterwarnings("ignore")

DB_PATH = Path(__file__).parent / "data" / "messages.db"

_TEMPLATE_MARKERS = [
    "Click here", "NUSConfessIT_bot",
    "👇 Comment **below** anonymously",
    "😆 Send an **anonymous message**",
    "Send an **anonymous message**",
    "PM THIS", "PM Confessor",
    "post a confession", "post **YOUR OWN** confession",
    "post your own anonymous",
]

def _is_template_line(line):
    s = line.strip()
    return bool(s) and any(m in s for m in _TEMPLATE_MARKERS)

def clean_body(text):
    if not text: return None
    lines = text.strip().split("\n")
    for i, line in enumerate(lines):
        if _is_template_line(line):
            if i == 0: return None
            return "\n".join(lines[:i]).strip() or None
    return text.strip()

def extract_confession_text(raw):
    if not raw: return None
    m = re.search(r"---\s*\n(.*?)\n---", raw, re.DOTALL)
    return m.group(1).strip() if m else clean_body(raw)

NUS_EXAM_PERIODS = [
    ("2024-04-22","2024-05-11"),("2024-11-25","2024-12-14"),
    ("2025-04-21","2025-05-10"),("2025-11-24","2025-12-13"),
    ("2026-04-20","2026-05-09"),
]
NUS_RECESS = [
    ("2024-03-04","2024-03-10"),("2024-10-07","2024-10-13"),
    ("2025-03-03","2025-03-09"),("2025-10-06","2025-10-12"),
    ("2026-03-02","2026-03-08"),
]

def in_range(d, ranges):
    try:
        dt = datetime.fromisoformat(d).date()
        for s,e in ranges:
            if datetime.strptime(s,"%Y-%m-%d").date() <= dt <= datetime.strptime(e,"%Y-%m-%d").date():
                return 1
    except: pass
    return 0

def flesch_score(text):
    if not text or len(text) < 10: return 0.0
    words = text.split()
    if not words: return 0.0
    sents = max(len(re.split(r'[.!?]+', text)), 1)
    syls = sum(max(1, len(re.findall(r'[aeiouy]+', w.lower()))) for w in words)
    return max(0, 206.835 - 1.015*(len(words)/sents) - 84.6*(syls/len(words)))

# ─── Build dataframe ────────────────────────────────────────────────────────

def build_df():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT id, date,
               COALESCE(NULLIF(content,''), NULLIF(text,'')) AS raw_body,
               text, forwards, reactions_count, reply_count
        FROM messages
        WHERE is_reply=0 AND COALESCE(NULLIF(content,''),NULLIF(text,'')) IS NOT NULL
        ORDER BY date DESC
    """).fetchall()
    conn.close()

    sia = SentimentIntensityAnalyzer()
    recs = []

    for (pid, date, raw_body, raw_text, forwards, reactions, rcount) in rows:
        conf = extract_confession_text(raw_body)
        if not conf or len(conf) < 10: continue
        if sum(c.isalpha() for c in conf)/max(len(conf),1) < 0.2: continue

        sent = sia.polarity_scores(conf)
        words = conf.split()
        hour = -1; dow = -1; month = -1
        try:
            dt = datetime.fromisoformat(date)
            hour, dow, month = dt.hour, dt.weekday(), dt.month
        except: pass

        m = re.search(r"\*\*#(\w+)\*\*", raw_text or raw_body)
        cat = m.group(1).lower() if m else "unknown"

        recs.append({
            "confession_text": conf, "category": cat,
            "hour": hour, "day_of_week": dow, "month": month,
            "forwards": forwards or 0,
            "word_count": len(words), "char_count": len(conf),
            "avg_word_len": sum(len(w) for w in words)/max(len(words),1),
            "has_question": int("?" in conf),
            "exclamation_count": conf.count("!"),
            "caps_ratio": sum(c.isupper() for c in conf if c.isalpha())/max(sum(1 for c in conf if c.isalpha()),1),
            "emoji_count": sum(1 for c in conf if ord(c)>0x1F300),
            "sentiment_pos": round(sent["pos"],4), "sentiment_neg": round(sent["neg"],4),
            "sentiment_neu": round(sent["neu"],4), "sentiment_compound": round(sent["compound"],4),
            "is_night": int(hour<6 or hour>=22),
            "is_weekend": int(dow>=5),
            "is_exam": in_range(date, NUS_EXAM_PERIODS),
            "is_recess": in_range(date, NUS_RECESS),
            "unique_word_ratio": len(set(w.lower() for w in words))/max(len(words),1),
            "punct_ratio": sum(1 for c in conf if c in ".,;:!?'\"-")/max(len(conf),1),
            "url_count": len(re.findall(r'https?://\S+', conf)),
            "line_count": conf.count("\n")+1,
            "flesch": round(flesch_score(conf),2),
            "sentiment_abs": round(abs(sent["compound"]),4),
            "has_media": int("[GIF]" in conf or "[Photo]" in conf or "[Video]" in conf or "t.me/" in conf),
            "reply_per_word": (rcount or 0)/max(len(words),1),
            "reactions_count": reactions or 0,
            "reply_count": rcount or 0,
        })

    return pd.DataFrame(recs)

# ─── Feature pipeline ───────────────────────────────────────────────────────

META_COLS = [
    "hour","day_of_week","month","word_count","char_count","avg_word_len",
    "has_question","exclamation_count","caps_ratio","emoji_count",
    "sentiment_pos","sentiment_neg","sentiment_neu","sentiment_compound",
    "is_night","is_weekend","is_exam","is_recess",
    "unique_word_ratio","punct_ratio","url_count","line_count",
    "flesch","sentiment_abs","has_media","reply_per_word",
]

class MetaExtractor(BaseEstimator, TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X[META_COLS].values.astype(float)

class CatEncoder(BaseEstimator, TransformerMixin):
    def fit(self,X,y=None):
        self.cats_ = sorted(X["category"].unique()); return self
    def transform(self,X):
        arr = np.zeros((len(X),len(self.cats_)), dtype=float)
        for i,cat in enumerate(X["category"]):
            if cat in self.cats_:
                arr[i,self.cats_.index(cat)] = 1.0
        return arr

class TextSel(BaseEstimator, TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X["confession_text"].fillna("").values

TFIDF_KW = dict(ngram_range=(1,2), max_features=8000,
                sublinear_tf=True, min_df=3, max_df=0.85)

def make_pipe(clf, scale=True):
    steps = [
        ("feat", FeatureUnion([
            ("txt", Pipeline([("sel",TextSel()),("tfidf",TfidfVectorizer(**TFIDF_KW))])),
            ("meta", MetaExtractor()),
            ("cat", CatEncoder()),
        ])),
    ]
    if scale: steps.append(("scl", StandardScaler(with_mean=False)))
    steps.append(("clf", clf))
    return Pipeline(steps)

def get_models():
    return {
        "ridge": make_pipe(Ridge(alpha=0.5), True),
        "huber": make_pipe(HuberRegressor(alpha=0.001, max_iter=200), True),
        "lightgbm": make_pipe(lgb.LGBMRegressor(n_estimators=150, max_depth=6,
                              learning_rate=0.1, random_state=42, n_jobs=1,
                              verbose=-1, subsample=0.85, colsample_bytree=0.8), False),
        "xgboost": make_pipe(xgb.XGBRegressor(n_estimators=150, max_depth=5,
                            learning_rate=0.1, eval_metric="rmse", random_state=42,
                            n_jobs=1, subsample=0.85, colsample_bytree=0.8), False),
    }

# ─── Run experiments ────────────────────────────────────────────────────────

def run_reg(name, pipe, df, y, cv, suffix=""):
    print(f"  {name}{suffix}...", flush=True)
    y_t = y
    back_transform = lambda x: x
    if suffix == "_log":
        y_t = np.log1p(y)
        back_transform = lambda p: np.expm1(np.clip(p, -10, 10))
    elif suffix == "_bc":
        ys = y + 1
        yt, lam = boxcox(ys)
        y_t = yt
        b_lambda = lam
        def back_transform(p):
            # Safe back-transform: clip so (p*lam+1) stays positive
            if abs(b_lambda) < 1e-6:
                return np.exp(p) - 1
            min_safe = -1.0 / b_lambda + 1e-6
            clipped = np.clip(p, min_safe, None)
            return np.maximum((clipped * b_lambda + 1) ** (1.0 / b_lambda) - 1, 0)

    y_pred_t = cross_val_predict(pipe, df, y_t, cv=cv, n_jobs=1, method="predict")
    y_pred = back_transform(y_pred_t)

    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    r2 = r2_score(y, y_pred)

    print(f"    MAE={mae:.2f}  RMSE={rmse:.2f}  R²={r2:.4f}")
    return {"model": f"{name}{suffix}", "mae": round(mae,4), "rmse": round(rmse,4), "r2": round(r2,4)}

def run_ensemble(df, y, cv):
    print("  ensemble(lgb+xgb+histgb_log)...", flush=True)
    y_log = np.log1p(y)
    preds = []
    for name, pipe in get_models().items():
        if name not in ("lightgbm","xgboost"): continue
        p = cross_val_predict(pipe, df, y_log, cv=cv, n_jobs=1, method="predict")
        preds.append(p)
    y_pred = np.expm1(np.clip(np.mean(preds, axis=0), -10, 10))
    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    r2 = r2_score(y, y_pred)
    print(f"    MAE={mae:.2f}  RMSE={rmse:.2f}  R²={r2:.4f}")
    return {"model":"ensemble_lgbm_xgb_log","mae":round(mae,4),"rmse":round(rmse,4),"r2":round(r2,4)}

def run_v1_comparison(df):
    """Run v1-style comparison: bare unigrams, no new features, for fair comparison."""
    print("\n--- V1 BASELINE (unigrams only, basic metadata) ---")
    v1_meta = ["hour","day_of_week","word_count","char_count","avg_word_len",
               "has_question","exclamation_count","caps_ratio","emoji_count",
               "sentiment_pos","sentiment_neg","sentiment_neu","sentiment_compound"]

    class MetaV1(BaseEstimator, TransformerMixin):
        def fit(self,X,y=None): return self
        def transform(self,X): return X[v1_meta].values.astype(float)

    pipe = Pipeline([
        ("feat", FeatureUnion([
            ("txt", Pipeline([("sel",TextSel()),
                              ("tfidf",TfidfVectorizer(ngram_range=(1,1),max_features=3000,
                                                       sublinear_tf=True,min_df=3))])),
            ("meta", MetaV1()),
            ("cat", CatEncoder()),
        ])),
        ("clf", lgb.LGBMRegressor(n_estimators=80, max_depth=4, learning_rate=0.15,
                                   random_state=42, n_jobs=1, verbose=-1)),
    ])

    y = df["reactions_count"].values.astype(float)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    # Raw
    y_pred = cross_val_predict(pipe, df, y, cv=cv, n_jobs=1)
    print(f"  raw:   MAE={mean_absolute_error(y,y_pred):.2f}  R²={r2_score(y,y_pred):.4f}")

    # Log
    y_log = np.log1p(y)
    y_pred_l = cross_val_predict(pipe, df, y_log, cv=cv, n_jobs=1)
    y_pred_bt = np.expm1(np.clip(y_pred_l, -10, 10))
    print(f"  log1p: MAE={mean_absolute_error(y,y_pred_bt):.2f}  R²={r2_score(y,y_pred_bt):.4f}")


# ─── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building dataset...", flush=True)
    df = build_df()
    y = df["reactions_count"].values.astype(float)
    print(f"{len(df)} posts, median={np.median(y):.0f}, max={int(y.max())}")
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    models = get_models()

    # V1 baseline on same data for fair comparison
    run_v1_comparison(df)

    print("\n--- V2 REGRESSION (raw) ---")
    raw_results = []
    for name, pipe in models.items():
        r = run_reg(name, pipe, df, y, cv)
        raw_results.append(r)

    print("\n--- V2 REGRESSION (log1p) ---")
    log_results = []
    for name, pipe in models.items():
        r = run_reg(name, pipe, df, y, cv, "_log")
        log_results.append(r)

    print("\n--- V2 REGRESSION (Box-Cox) ---")
    bc_results = []
    for name, pipe in models.items():
        r = run_reg(name, pipe, df, y, cv, "_bc")
        bc_results.append(r)

    print("\n--- ENSEMBLE ---")
    ensemble_result = run_ensemble(df, y, cv)

    # Summary
    print("\n" + "="*60)
    print("V1 vs V2 COMPARISON")
    print("="*60)
    print("\n--- RAW MAE ---")
    for r in sorted(raw_results, key=lambda x: x["mae"]):
        print(f"  {r['model']:<25} MAE={r['mae']:.2f}  R²={r['r2']:.4f}")
    print("\n--- LOG1P (back-transformed MAE) ---")
    for r in sorted(log_results, key=lambda x: x["mae"]):
        print(f"  {r['model']:<25} MAE={r['mae']:.2f}  R²={r['r2']:.4f}")
    print("\n--- BOX-COX (back-transformed MAE) ---")
    for r in sorted(bc_results, key=lambda x: x["mae"]):
        print(f"  {r['model']:<25} MAE={r['mae']:.2f}  R²={r['r2']:.4f}")
    print(f"\n--- ENSEMBLE ---")
    print(f"  {ensemble_result['model']:<25} MAE={ensemble_result['mae']:.2f}  R²={ensemble_result['r2']:.4f}")