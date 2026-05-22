#!/usr/bin/env python3
"""Generate sentence embeddings via OpenRouter, then train classifier."""

import os, sys, json, warnings, re, sqlite3, time
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import numpy as np
import pandas as pd

from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import StandardScaler
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score, confusion_matrix
import lightgbm as lgb

warnings.filterwarnings("ignore")
DB_PATH = Path(__file__).parent / "data" / "messages.db"
EMBED_PATH = Path(__file__).parent / "data" / "embeddings_v5.npy"
EMBED_IDS_PATH = Path(__file__).parent / "data" / "embedding_ids_v5.npy"

# Load API key — try Hermes env first, then project .env
ENV_PATHS = [
    Path.home() / ".hermes" / ".env",
    Path(__file__).parent / ".env",
]
API_KEY = None

for env_path in ENV_PATHS:
    if not env_path.exists():
        continue
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass
    # Check both possible key names
    for var in ["OPENROUTER_API_KEY", "OPENAI_API_KEY"]:
        val = os.environ.get(var)
        if val:
            API_KEY = val
            print(f"  Using {var} from {env_path.name}", flush=True)
            break
    if API_KEY:
        break

if not API_KEY:
    print("ERROR: No API key found. Set OPENROUTER_API_KEY in ~/.hermes/.env")
    sys.exit(1)

# ─── Data loading ────────────────────────────────────────────────────────────

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

# ─── Embeddings via OpenRouter ──────────────────────────────────────────────

def get_embeddings(texts: list[str], model="openai/text-embedding-3-small",
                   dimensions=512, batch_size=256, max_retries=3):
    """Generate embeddings via OpenRouter API. Returns (N, dims) array."""
    all_embeddings = []
    total = len(texts)
    print(f"  Generating embeddings for {total} texts ({model}, {dimensions}d)...", flush=True)

    for i in range(0, total, batch_size):
        batch = texts[i:i+batch_size]
        payload = json.dumps({
            "model": model,
            "input": batch,
            "dimensions": dimensions,
        }).encode()

        for attempt in range(max_retries):
            try:
                req = Request(
                    "https://openrouter.ai/api/v1/embeddings",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
                with urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read())
                batch_emb = [d["embedding"] for d in result["data"]]
                all_embeddings.extend(batch_emb)
                print(f"    [{i}/{total}] got {len(batch_emb)} embeddings", flush=True)
                break
            except HTTPError as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"    retry {attempt+1}/{max_retries} after {wait}s (HTTP {e.code})", flush=True)
                    time.sleep(wait)
                else:
                    print(f"    FAILED at batch {i}: HTTP {e.code} {e.read().decode()[:200]}", flush=True)
                    raise
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"    retry after {wait}s: {e}", flush=True)
                    time.sleep(wait)
                else:
                    raise

        # Rate limiting — be nice
        if i + batch_size < total:
            time.sleep(0.1)

    return np.array(all_embeddings, dtype=np.float32)


# ─── Pipeline ────────────────────────────────────────────────────────────────

META_COLS = ["hour","dow","month","in","iw","wc","cc"]

class MetaExt(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X[META_COLS].values.astype(float)

class CatEnc(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None):
        self.cats_=sorted(X["cat"].unique()); return self
    def transform(self,X):
        a=np.zeros((len(X),len(self.cats_)),dtype=float)
        for i,c in enumerate(X["cat"]):
            if c in self.cats_: a[i,self.cats_.index(c)]=1.0
        return a

def make_pipe_embeddings():
    """Classifier using pre-computed embeddings (ndarray) + meta + cats."""
    class EmbedFeat(BaseEstimator,TransformerMixin):
        def __init__(self, embeddings):
            self.embeddings = embeddings
        def fit(self,X,y=None): return self
        def transform(self,X):
            return self.embeddings

    return Pipeline([
        ("feat", FeatureUnion([
            ("emb", Pipeline([
                ("pass", "passthrough"),  # dummy — we feed embeddings directly
            ])),
            ("meta", MetaExt()),
            ("cat", CatEnc()),
        ])),
        ("clf", lgb.LGBMClassifier(
            n_estimators=150, max_depth=6, learning_rate=0.1,
            random_state=42, n_jobs=1, verbose=-1,
            subsample=0.85, colsample_bytree=0.8, class_weight="balanced")),
    ])

# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building dataset...", flush=True)
    df = build_df()
    y = df["viral"].values
    texts = df["txt"].tolist()
    ids = df["id"].values
    print(f"{len(df)} posts, viral rate={y.mean():.1%}", flush=True)

    # ── 1. Generate or load embeddings ──
    if EMBED_PATH.exists() and EMBED_IDS_PATH.exists():
        cached_ids = np.load(EMBED_IDS_PATH)
        if len(cached_ids) == len(ids) and np.array_equal(cached_ids, ids):
            print("Loading cached embeddings...", flush=True)
            embeddings = np.load(EMBED_PATH)
        else:
            print("Cached embeddings don't match IDs. Regenerating...", flush=True)
            embeddings = get_embeddings(texts)
            np.save(EMBED_PATH, embeddings)
            np.save(EMBED_IDS_PATH, ids)
    else:
        embeddings = get_embeddings(texts)
        np.save(EMBED_PATH, embeddings)
        np.save(EMBED_IDS_PATH, ids)

    print(f"Embeddings shape: {embeddings.shape}", flush=True)

    # ── 2. Train classifier with embeddings ──
    print("\nTraining LightGBM with embeddings...", flush=True)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # We need to pass embeddings through CV properly.
    # Build a custom pipeline that uses the embeddings directly.
    # For cross_val_predict, we need the embeddings to be part of X.
    # Simplest: create a wrapper DataFrame that includes both text features and metadata.

    # Actually, let me just concatenate embeddings + meta + cats manually for CV.
    # First get the metadata and category arrays
    cat_enc = CatEnc()
    cat_feats = cat_enc.fit_transform(df)
    meta_feats = df[META_COLS].values.astype(float)

    # Concatenate all features: embeddings + meta + cats
    X_all = np.concatenate([embeddings, meta_feats, cat_feats], axis=1)
    print(f"Feature matrix shape: {X_all.shape}", flush=True)

    # Standardize meta features (but not embeddings — they're already normalized)
    scaler = StandardScaler()
    # Only scale meta columns (indices after embeddings)
    n_emb = embeddings.shape[1]
    n_meta = len(META_COLS)
    n_cat = cat_feats.shape[1]
    # Scale everything except embeddings (they're already unit vectors)
    X_scaled = X_all.copy()
    X_scaled[:, n_emb:] = scaler.fit_transform(X_all[:, n_emb:])

    clf = lgb.LGBMClassifier(
        n_estimators=150, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=1, verbose=-1,
        subsample=0.85, colsample_bytree=0.8, class_weight="balanced",
    )

    y_pred = cross_val_predict(clf, X_scaled, y, cv=cv, n_jobs=1, method="predict")
    y_proba = cross_val_predict(clf, X_scaled, y, cv=cv, n_jobs=1, method="predict_proba")[:, 1]

    precision = precision_score(y, y_pred)
    recall = recall_score(y, y_pred)
    f1 = f1_score(y, y_pred)
    roc_auc = roc_auc_score(y, y_proba)
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()

    print(f"\n--- Performance (embeddings + meta) ---")
    print(f"  ROC-AUC:  {roc_auc:.3f}")
    print(f"  F1:       {f1:.3f}")
    print(f"  Precision:{precision:.3f}")
    print(f"  Recall:   {recall:.3f}")
    print(f"  TN={tn} FP={fp} FN={fn} TP={tp}")
    print(f"  Accuracy: {(tn+tp)/(tn+fp+fn+tp):.3f}")

    # Also try embeddings-only
    clf_emb_only = lgb.LGBMClassifier(
        n_estimators=150, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=1, verbose=-1,
        subsample=0.85, colsample_bytree=0.8, class_weight="balanced",
    )
    y_pred_eo = cross_val_predict(clf_emb_only, embeddings, y, cv=cv, n_jobs=1, method="predict")
    y_proba_eo = cross_val_predict(clf_emb_only, embeddings, y, cv=cv, n_jobs=1, method="predict_proba")[:,1]

    print(f"\n--- Performance (embeddings only) ---")
    print(f"  ROC-AUC:  {roc_auc_score(y, y_proba_eo):.3f}")
    print(f"  F1:       {f1_score(y, y_pred_eo):.3f}")
    print(f"  Precision:{precision_score(y, y_pred_eo):.3f}")
    print(f"  Recall:   {recall_score(y, y_pred_eo):.3f}")

    # ── 3. Compare with v4 ──
    print(f"\n=== COMPARISON ===")
    print(f"  v4 (TF-IDF 8k + meta):        AUC=0.774  F1=0.545")
    print(f"  v5 (embeddings only):          AUC={roc_auc_score(y, y_proba_eo):.3f}  F1={f1_score(y, y_pred_eo):.3f}")
    print(f"  v5 (embeddings + meta + cats): AUC={roc_auc:.3f}  F1={f1:.3f}")