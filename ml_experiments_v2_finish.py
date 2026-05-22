#!/usr/bin/env python3
"""Finish the remaining experiments: XGBoost log, ensemble, and PCA variants."""

import sys, csv, warnings, re, sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import Ridge, HuberRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import lightgbm as lgb
import xgboost as xgb

warnings.filterwarnings("ignore")
DB_PATH = Path(__file__).parent / "data" / "messages.db"

# ─── Data loading (same as before) ───────────────────────────────────────────

_TEMPLATE_MARKERS = [
    "Click here", "NUSConfessIT_bot",
    "👇 Comment **below** anonymously",
    "😆 Send an **anonymous message**",
    "Send an **anonymous message**",
    "PM THIS", "PM Confessor",
    "post a confession", "post **YOUR OWN** confession",
    "post your own anonymous",
]
def _is_template_line(l):
    s=l.strip(); return bool(s) and any(m in s for m in _TEMPLATE_MARKERS)
def clean_body(t):
    if not t: return None
    ls=t.strip().split("\n")
    for i,l in enumerate(ls):
        if _is_template_line(l):
            if i==0: return None
            return "\n".join(ls[:i]).strip() or None
    return t.strip()
def extract_confession_text(r):
    if not r: return None
    m=re.search(r"---\s*\n(.*?)\n---",r,re.DOTALL)
    return m.group(1).strip() if m else clean_body(r)

NUS_EXAM=[("2024-04-22","2024-05-11"),("2024-11-25","2024-12-14"),
          ("2025-04-21","2025-05-10"),("2025-11-24","2025-12-13"),
          ("2026-04-20","2026-05-09")]
NUS_RECESS=[("2024-03-04","2024-03-10"),("2024-10-07","2024-10-13"),
            ("2025-03-03","2025-03-09"),("2025-10-06","2025-10-12"),
            ("2026-03-02","2026-03-08")]
def in_range(d,ranges):
    try:
        dt=datetime.fromisoformat(d).date()
        for s,e in ranges:
            if datetime.strptime(s,"%Y-%m-%d").date()<=dt<=datetime.strptime(e,"%Y-%m-%d").date(): return 1
    except: pass
    return 0
def flesch(t):
    if not t or len(t)<10: return 0.0
    w=t.split()
    if not w: return 0.0
    s=max(len(re.split(r'[.!?]+',t)),1)
    sy=sum(max(1,len(re.findall(r'[aeiouy]+',ww.lower()))) for ww in w)
    return max(0,206.835-1.015*(len(w)/s)-84.6*(sy/len(w)))

def build_df():
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("""
        SELECT id, date, COALESCE(NULLIF(content,''),NULLIF(text,'')) AS raw_body,
               text, forwards, reactions_count, reply_count
        FROM messages WHERE is_reply=0
          AND COALESCE(NULLIF(content,''),NULLIF(text,'')) IS NOT NULL
        ORDER BY date DESC
    """).fetchall()
    conn.close()
    sia=SentimentIntensityAnalyzer()
    recs=[]
    for (pid,date,raw_body,raw_text,forwards,reactions,rcount) in rows:
        conf=extract_confession_text(raw_body)
        if not conf or len(conf)<10: continue
        if sum(c.isalpha() for c in conf)/max(len(conf),1)<0.2: continue
        sent=sia.polarity_scores(conf)
        words=conf.split()
        hour=dow=month=-1
        try: dt=datetime.fromisoformat(date); hour, dow, month = dt.hour, dt.weekday(), dt.month
        except: pass
        m=re.search(r"\*\*#(\w+)\*\*",raw_text or raw_body)
        cat=m.group(1).lower() if m else "unknown"
        recs.append({
            "confession_text":conf,"category":cat,
            "hour":hour,"day_of_week":dow,"month":month,
            "forwards":forwards or 0,
            "word_count":len(words),"char_count":len(conf),
            "avg_word_len":sum(len(w) for w in words)/max(len(words),1),
            "has_question":int("?" in conf),"exclamation_count":conf.count("!"),
            "caps_ratio":sum(c.isupper() for c in conf if c.isalpha())/max(sum(1 for c in conf if c.isalpha()),1),
            "emoji_count":sum(1 for c in conf if ord(c)>0x1F300),
            "sentiment_pos":round(sent["pos"],4),"sentiment_neg":round(sent["neg"],4),
            "sentiment_neu":round(sent["neu"],4),"sentiment_compound":round(sent["compound"],4),
            "is_night":int(hour<6 or hour>=22),"is_weekend":int(dow>=5),
            "is_exam":in_range(date,NUS_EXAM),"is_recess":in_range(date,NUS_RECESS),
            "unique_word_ratio":len(set(w.lower() for w in words))/max(len(words),1),
            "punct_ratio":sum(1 for c in conf if c in ".,;:!?'\"-")/max(len(conf),1),
            "url_count":len(re.findall(r'https?://\S+',conf)),
            "line_count":conf.count("\n")+1,
            "flesch":round(flesch(conf),2),"sentiment_abs":round(abs(sent["compound"]),4),
            "has_media":int("[GIF]" in conf or "[Photo]" in conf or "[Video]" in conf or "t.me/" in conf),
            "reply_per_word":(rcount or 0)/max(len(words),1),
            "reactions_count":reactions or 0,"reply_count":rcount or 0,
        })
    return pd.DataFrame(recs)

# ─── Feature pipeline ────────────────────────────────────────────────────────

META_COLS = ["hour","day_of_week","month","word_count","char_count","avg_word_len",
    "has_question","exclamation_count","caps_ratio","emoji_count",
    "sentiment_pos","sentiment_neg","sentiment_neu","sentiment_compound",
    "is_night","is_weekend","is_exam","is_recess",
    "unique_word_ratio","punct_ratio","url_count","line_count",
    "flesch","sentiment_abs","has_media","reply_per_word"]

class MetaExt(BaseEstimator, TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X[META_COLS].values.astype(float)
class CatEnc(BaseEstimator, TransformerMixin):
    def fit(self,X,y=None):
        self.cats_=sorted(X["category"].unique()); return self
    def transform(self,X):
        a=np.zeros((len(X),len(self.cats_)),dtype=float)
        for i,cat in enumerate(X["category"]):
            if cat in self.cats_: a[i,self.cats_.index(cat)]=1.0
        return a
class TextSel(BaseEstimator, TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X["confession_text"].fillna("").values

TFIDF_KW = dict(ngram_range=(1,2), max_features=8000, sublinear_tf=True, min_df=3, max_df=0.85)

def make_pipe(clf, scale=True, n_pca=None):
    """If n_pca is set, insert TruncatedSVD between TF-IDF and the rest."""
    steps = [("feat", FeatureUnion([
        ("txt", Pipeline([
            ("sel", TextSel()),
            ("tfidf", TfidfVectorizer(**TFIDF_KW)),
        ])),
        ("meta", MetaExt()),
        ("cat", CatEnc()),
    ]))]
    if n_pca:
        # SVD on the sparse TF-IDF only — can't put it after FeatureUnion
        # because the meta/cat features are dense and small
        # Better approach: SVD only on text features, concat with meta later
        steps = [
            ("txt_pipe", Pipeline([
                ("sel", TextSel()),
                ("tfidf", TfidfVectorizer(**TFIDF_KW)),
            ])),
        ]
        # Build a manual pipeline: SVD on text -> hstack with meta+cat
        # Build a manual pipeline: SVD on text -> hstack with meta+cat
        # FeatureUnion handles this if we put SVD inside the text branch
        steps = [("feat", FeatureUnion([
            ("txt_svd", Pipeline([
                ("sel", TextSel()),
                ("tfidf", TfidfVectorizer(**TFIDF_KW)),
                ("svd", TruncatedSVD(n_components=n_pca, random_state=42)),
            ])),
            ("meta", MetaExt()),
            ("cat", CatEnc()),
        ]))]
    if scale: steps.append(("scl", StandardScaler(with_mean=False)))
    steps.append(("clf", clf))
    return Pipeline(steps)

# ─── Models ──────────────────────────────────────────────────────────────────

def get_models(pca=None):
    suffix = f"_pca{pca}" if pca else ""
    return {
        f"ridge{suffix}": make_pipe(Ridge(alpha=0.5), True, pca),
        f"huber{suffix}": make_pipe(HuberRegressor(alpha=0.001, max_iter=200), True, pca),
        f"lightgbm{suffix}": make_pipe(
            lgb.LGBMRegressor(n_estimators=150, max_depth=6, learning_rate=0.1,
                              random_state=42, n_jobs=1, verbose=-1,
                              subsample=0.85, colsample_bytree=0.8), False, pca),
        f"xgboost{suffix}": make_pipe(
            xgb.XGBRegressor(n_estimators=150, max_depth=5, learning_rate=0.1,
                             eval_metric="rmse", random_state=42, n_jobs=1,
                             subsample=0.85, colsample_bytree=0.8), False, pca),
    }

def run_one(name, pipe, df, y, cv, suffix=""):
    print(f"  {name}...", flush=True)
    y_t = y
    bt = lambda p: p
    if suffix == "_log":
        y_t = np.log1p(y)
        bt = lambda p: np.expm1(np.clip(p, -10, 10))

    y_pred_t = cross_val_predict(pipe, df, y_t, cv=cv, n_jobs=1, method="predict")
    y_pred = bt(y_pred_t)
    mae = mean_absolute_error(y, y_pred)
    r2 = r2_score(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    print(f"    MAE={mae:.2f}  RMSE={rmse:.2f}  R²={r2:.4f}", flush=True)
    return {"model": name, "mae": round(mae,4), "rmse": round(rmse,4), "r2": round(r2,4)}

def run_ensemble(df, y, cv, label="ensemble_log"):
    print(f"  {label}...", flush=True)
    y_log = np.log1p(y)
    preds = []
    for name, pipe in get_models().items():
        if "lightgbm" not in name and "xgboost" not in name: continue
        p = cross_val_predict(pipe, df, y_log, cv=cv, n_jobs=1, method="predict")
        preds.append(p)
    y_pred = np.expm1(np.clip(np.mean(preds, axis=0), -10, 10))
    mae = mean_absolute_error(y, y_pred)
    r2 = r2_score(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    print(f"    MAE={mae:.2f}  RMSE={rmse:.2f}  R²={r2:.4f}", flush=True)
    return {"model": label, "mae": round(mae,4), "rmse": round(rmse,4), "r2": round(r2,4)}

# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building dataset...", flush=True)
    df = build_df()
    y = df["reactions_count"].values.astype(float)
    print(f"{len(df)} posts, median={np.median(y):.0f}, mean={np.mean(y):.1f}, max={int(y.max())}", flush=True)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    all_results = []

    # 1. Finish what was killed: XGBoost log + ensemble
    print("\n=== XGBoost log (finishing) ===", flush=True)
    models_xgb_log = {"xgboost_log": make_pipe(
        xgb.XGBRegressor(n_estimators=150, max_depth=5, learning_rate=0.1,
                         eval_metric="rmse", random_state=42, n_jobs=1,
                         subsample=0.85, colsample_bytree=0.8), False)}
    for n,p in models_xgb_log.items():
        all_results.append(run_one(n, p, df, y, cv, "_log"))

    print("\n=== Ensemble (lgbm + xgb, log1p) ===", flush=True)
    all_results.append(run_ensemble(df, y, cv))

    # 2. PCA variants — try different component counts
    for n_comp in [50, 100, 200, 500]:
        print(f"\n=== PCA n_components={n_comp} (raw) ===", flush=True)
        models_pca = get_models(pca=n_comp)
        for n,p in models_pca.items():
            all_results.append(run_one(n, p, df, y, cv, ""))

        print(f"\n=== PCA n_components={n_comp} (log1p) ===", flush=True)
        for n,p in models_pca.items():
            all_results.append(run_one(n, p, df, y, cv, "_log"))

    # 3. Summary
    print("\n" + "="*70)
    print("FINAL LEADERBOARD (all models)")
    print("="*70)
    results_df = pd.DataFrame(all_results).sort_values("mae", ascending=True)
    print()
    print(results_df.to_string(index=False))
    print()
    print("Best 5:")
    for _, r in results_df.head(5).iterrows():
        print(f"  {r['model']:<30} MAE={r['mae']:.2f}  R²={r['r2']:.4f}")