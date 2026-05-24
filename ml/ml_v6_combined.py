#!/usr/bin/env python3
"""v6: Embeddings + TF-IDF combined + hyperparameter grid search."""

import os, sys, warnings, re, sqlite3, time
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.sparse import hstack, csr_matrix
from dotenv import load_dotenv

from sklearn.model_selection import StratifiedKFold, RandomizedSearchCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score, confusion_matrix
import lightgbm as lgb

warnings.filterwarnings("ignore")
DB_PATH = Path(__file__).parent / "data" / "messages.db"
EMBED_PATH = Path(__file__).parent / "data" / "embeddings_v5.npy"
EMBED_IDS_PATH = Path(__file__).parent / "data" / "embedding_ids_v5.npy"

# ─── Data ────────────────────────────────────────────────────────────────────

_TEMPLATE_MARKERS = [
    "Click here", "NUSConfessIT_bot",
    "👇 Comment **below** anonymously", "😆 Send an **anonymous message**",
    "Send an **anonymous message**", "PM THIS", "PM Confessor",
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

HELIX_KW=["helix","Helix","helix house","Helix House"]
def is_helix(t, rb):
    c=f"{t or ''} {rb or ''}"; return any(k in c for k in HELIX_KW)

def build_df():
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("""SELECT id,date,COALESCE(NULLIF(content,''),NULLIF(text,'')) AS rb,
           text,forwards,reactions_count,reply_count FROM messages WHERE is_reply=0
           AND COALESCE(NULLIF(content,''),NULLIF(text,'')) IS NOT NULL""").fetchall()
    conn.close()
    recs=[]
    for (pid,date,rb,rt,fw,rc,rpc) in rows:
        conf=extract_confession_text(rb)
        if not conf or len(conf)<10: continue
        if sum(c.isalpha() for c in conf)/max(len(conf),1)<0.2: continue
        if is_helix(rt,rb): continue
        h=dw=mo=-1
        try: dt=datetime.fromisoformat(date); h,dw,mo=dt.hour,dt.weekday(),dt.month
        except: pass
        m=re.search(r"\*\*#(\w+)\*\*",rt or rb)
        cat=m.group(1).lower() if m else "unknown"
        recs.append({
            "id": pid, "txt": conf, "cat": cat,
            "hour": h, "dow": dw, "month": mo,
            "in": int(h<6 or h>=22), "iw": int(dw>=5),
            "wc": len(conf.split()), "cc": len(conf),
            "rc": rc or 0, "rpc": rpc or 0, "fw": fw or 0,
        })
    df=pd.DataFrame(recs)
    df["vs"] = (df["rc"]*1 + df["rpc"]*2 + df["fw"]*3) / 6
    th = df["vs"].quantile(0.75)
    df["viral"] = (df["vs"] >= th).astype(int)
    return df

# ─── CV evaluation ───────────────────────────────────────────────────────────

META_COLS = ["hour","dow","month","in","iw","wc","cc"]
CAT_COLS = ["cat"]

def build_feature_matrix(texts, embeddings, df, tfidf=None, fit=False):
    """Build combined feature matrix: TF-IDF + embeddings + meta + cats."""
    # TF-IDF
    if fit:
        tfidf = TfidfVectorizer(ngram_range=(1,2), max_features=8000,
                                sublinear_tf=True, min_df=3, max_df=0.85)
        X_tfidf = tfidf.fit_transform(texts)
    else:
        X_tfidf = tfidf.transform(texts)

    # Embeddings
    X_emb = csr_matrix(embeddings)

    # Metadata
    meta = df[META_COLS].values.astype(float)
    X_meta = csr_matrix(meta)

    # Categories — one-hot
    cats_enc = pd.get_dummies(df["cat"])
    X_cat = csr_matrix(cats_enc.values.astype(float))

    X = hstack([X_tfidf, X_emb, X_meta, X_cat])

    if fit:
        return X, tfidf, cats_enc.columns.tolist()
    return X

def evaluate(texts, embeddings, df, y, clf, label):
    """Manual 5-fold CV to avoid Pipeline headaches with precomputed embeddings."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    y_pred = np.zeros_like(y)
    y_proba = np.zeros_like(y, dtype=float)

    for fold, (train_idx, test_idx) in enumerate(cv.split(df, y)):
        print(f"  Fold {fold+1}/5...", flush=True)

        # Build train features
        X_train_txt = [texts[i] for i in train_idx]
        X_train, tfidf, _ = build_feature_matrix(
            X_train_txt, embeddings[train_idx], df.iloc[train_idx],
            fit=True
        )

        # Build test features with fitted tfidf
        X_test_txt = [texts[i] for i in test_idx]
        X_test = build_feature_matrix(
            X_test_txt, embeddings[test_idx], df.iloc[test_idx],
            tfidf=tfidf
        )

        clf.fit(X_train, y[train_idx])
        y_pred[test_idx] = clf.predict(X_test)
        y_proba[test_idx] = clf.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y, y_proba)
    f1 = f1_score(y, y_pred)
    prec = precision_score(y, y_pred)
    rec = recall_score(y, y_pred)
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()

    print(f"  {label}: AUC={auc:.3f} F1={f1:.3f} Prec={prec:.3f} Rec={rec:.3f}", flush=True)
    return {"model": label, "auc": round(auc,3), "f1": round(f1,3),
            "precision": round(prec,3), "recall": round(rec,3)}


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building dataset...", flush=True)
    df = build_df()
    y = df["viral"].values
    texts = df["txt"].tolist()
    print(f"{len(df)} posts, viral rate={y.mean():.1%}", flush=True)

    # Load embeddings
    if not EMBED_PATH.exists():
        print("ERROR: No embeddings found. Run ml_embeddings.py first.")
        sys.exit(1)
    embeddings = np.load(EMBED_PATH)
    print(f"Embeddings: {embeddings.shape}", flush=True)

    all_results = []

    # ── 1. Compare: embeddings alone vs embeddings+TF-IDF (default params) ──
    print("\n=== A: Default params comparison ===", flush=True)

    clf_default = lgb.LGBMClassifier(
        n_estimators=150, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=1, verbose=-1,
        subsample=0.85, colsample_bytree=0.8, class_weight="balanced",
    )

    # Embeddings + meta only (replicate v5b for fair comparison in this script)
    r = evaluate(texts, embeddings, df, y, clf_default, "emb+meta (default)")
    all_results.append(r)

    # Embeddings + TF-IDF + meta + cats (all together)
    r = evaluate(texts, embeddings, df, y, clf_default, "emb+tfidf+meta (default)")
    all_results.append(r)

    # ── 2. Hyperparameter search ──
    print("\n=== B: Randomized HP search on best combo ===", flush=True)

    # Use first fold only for HP search (a single train/test split)
    cv_search = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    train_idx, test_idx = list(cv_search.split(df, y))[0]

    X_train_txt = [texts[i] for i in train_idx]
    X_train_full, tfidf_hp, _ = build_feature_matrix(
        X_train_txt, embeddings[train_idx], df.iloc[train_idx],
        fit=True
    )
    X_test_txt = [texts[i] for i in test_idx]
    X_test_full = build_feature_matrix(
        X_test_txt, embeddings[test_idx], df.iloc[test_idx],
        tfidf=tfidf_hp
    )

    y_train = y[train_idx]
    y_test = y[test_idx]

    # Define search space — focused on most impactful params
    param_dist = {
        "n_estimators": [100, 150, 200, 300],
        "max_depth": [4, 6, 8, 10],
        "learning_rate": [0.03, 0.05, 0.08, 0.1, 0.15],
        "subsample": [0.6, 0.7, 0.8, 0.9, 1.0],
        "colsample_bytree": [0.6, 0.7, 0.8, 0.9, 1.0],
        "min_child_samples": [10, 20, 50],
        "reg_lambda": [0.0, 0.1, 0.5, 1.0],
        "reg_alpha": [0.0, 0.1, 0.5, 1.0],
    }

    base = lgb.LGBMClassifier(random_state=42, n_jobs=1, verbose=-1,
                               class_weight="balanced")

    search = RandomizedSearchCV(
        base, param_dist, n_iter=30, scoring="roc_auc",
        cv=3, random_state=42, n_jobs=1, verbose=0,
    )
    print("  Searching 30 random combos (3-fold CV on train set)...", flush=True)
    search.fit(X_train_full, y_train)

    best_params = search.best_params_
    print(f"\n  Best params: {best_params}", flush=True)
    print(f"  Best CV AUC (search): {search.best_score_:.4f}", flush=True)

    # ── 3. Evaluate best params on full 5-fold CV ──
    print("\n=== C: Best model (5-fold CV) ===", flush=True)

    clf_best = lgb.LGBMClassifier(
        random_state=42, n_jobs=1, verbose=-1,
        class_weight="balanced",
        **best_params,
    )

    r = evaluate(texts, embeddings, df, y, clf_best, "emb+tfidf+meta (tuned)")
    all_results.append(r)

    # ── 4. Compare all ──
    print("\n" + "="*60)
    print("FINAL COMPARISON")
    print("="*60)
    print(f"{'Model':<35} {'AUC':>6} {'F1':>6} {'Prec':>6} {'Rec':>6}")
    print("-"*60)
    baseline_v4 = {"model": "v4 TF-IDF+meta", "auc": 0.774, "f1": 0.545, "precision": 0.447, "recall": 0.697}
    all_models = [baseline_v4] + all_results
    for r in all_models:
        print(f"  {r['model']:<33} {r['auc']:>6.3f} {r['f1']:>6.3f} {r['precision']:>6.3f} {r['recall']:>6.3f}")
    print()
    best = max(all_results, key=lambda x: x['auc'])
    gain = (best['auc'] - baseline_v4['auc']) * 100
    print(f"  Best: {best['model']} — AUC={best['auc']:.3f} (+{gain:.1f}% vs v4)")