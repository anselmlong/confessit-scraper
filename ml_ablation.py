#!/usr/bin/env python3
"""Ablation study: measure ROC-AUC drop when removing feature groups."""

import warnings, re, sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score
import lightgbm as lgb

warnings.filterwarnings("ignore")
DB_PATH = Path(__file__).parent / "data" / "messages.db"

# ─── Data ────────────────────────────────────────────────────────────────────

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

HELIX_KW=["helix","Helix","helix house","Helix House"]
def is_helix(t, rb):
    c=f"{t or ''} {rb or ''}"; return any(k in c for k in HELIX_KW)

def build_df():
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("""SELECT id,date,COALESCE(NULLIF(content,''),NULLIF(text,'')) AS rb,
           text,forwards,reactions_count,reply_count FROM messages WHERE is_reply=0
           AND COALESCE(NULLIF(content,''),NULLIF(text,'')) IS NOT NULL""").fetchall()
    conn.close()
    sia=SentimentIntensityAnalyzer()
    recs=[]
    for (pid,date,rb,rt,fw,rc, rpc) in rows:
        conf=extract_confession_text(rb)
        if not conf or len(conf)<10: continue
        if sum(c.isalpha() for c in conf)/max(len(conf),1)<0.2: continue
        if is_helix(rt,rb): continue
        s=sia.polarity_scores(conf)
        w=conf.split()
        h=dw=mo=-1
        try: dt=datetime.fromisoformat(date); h,dw,mo=dt.hour,dt.weekday(),dt.month
        except: pass
        m=re.search(r"\*\*#(\w+)\*\*",rt or rb)
        cat=m.group(1).lower() if m else "unknown"
        recs.append({"txt":conf,"cat":cat,
            "hour":h,"dow":dw,"month":mo,
            "wc":len(w),"cc":len(conf),
            "awl":sum(len(x) for x in w)/max(len(w),1),
            "hq":int("?" in conf),"ec":conf.count("!"),
            "cr":sum(c.isupper() for c in conf if c.isalpha())/max(sum(1 for c in conf if c.isalpha()),1),
            "emc":sum(1 for c in conf if ord(c)>0x1F300),
            "sp":round(s["pos"],4),"sn":round(s["neg"],4),"sneu":round(s["neu"],4),
            "sc":round(s["compound"],4),
            "in":int(h<6 or h>=22),"iw":int(dw>=5),
            "ie":in_range(date,NUS_EXAM),"ir":in_range(date,NUS_RECESS),
            "uwr":len(set(w.lower() for w in w))/max(len(w),1),
            "pr":sum(1 for c in conf if c in ".,;:!?'\"-")/max(len(conf),1),
            "urc":len(re.findall(r'https?://\S+',conf)),
            "lc":conf.count("\n")+1,
            "fl":round(flesch(conf),2),"sa":round(abs(s["compound"]),4),
            "hm":int("[GIF]" in conf or "[Photo]" in conf or "[Video]" in conf or "t.me/" in conf),
            "vs":round((rc*1+rpc*2+fw*3)/6,2)})
    df=pd.DataFrame(recs)
    th=df["vs"].quantile(0.75)
    df["viral"]=(df["vs"]>=th).astype(int)
    return df

# ─── All metadata columns ────────────────────────────────────────────────────

ALL_META = ["hour","dow","month","wc","cc","awl",
    "hq","ec","cr","emc",
    "sp","sn","sneu","sc",
    "in","iw","ie","ir",
    "uwr","pr","urc","lc",
    "fl","sa","hm"]

# Feature groups for ablation
GROUPS = {
    "ALL": ALL_META,  # placeholder — means all features

    # Major blocks
    "text_stats": ["wc","cc","awl","lc"],
    "sentiment": ["sp","sn","sneu","sc","sa"],
    "time": ["hour","dow","month","in","iw"],
    "calendars": ["ie","ir"],
    "writing_style": ["hq","ec","cr","emc","uwr","pr","urc","hm","fl"],

    # Individual top features from v4
    "hour": ["hour"],
    "avg_word_len": ["awl"],
    "caps_ratio": ["cr"],
    "month": ["month"],
    "punct_ratio": ["pr"],
    "word_count": ["wc"],
    "flesch": ["fl"],
    "char_count": ["cc"],
}

class TextSel(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X["txt"].fillna("").values
class CatEnc(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None):
        self.cats_=sorted(X["cat"].unique()); return self
    def transform(self,X):
        a=np.zeros((len(X),len(self.cats_)),dtype=float)
        for i,c in enumerate(X["cat"]):
            if c in self.cats_: a[i,self.cats_.index(c)]=1.0
        return a

def make_pipe_with_meta(meta_cols):
    """Build pipeline using only the specified meta cols."""
    keep = set(meta_cols)

    class DynamicMeta(BaseEstimator,TransformerMixin):
        def fit(self,X,y=None): return self
        def transform(self,X):
            return X[[c for c in ALL_META if c in keep]].values.astype(float)

    steps = [("feat", FeatureUnion([
        ("txt", Pipeline([("sel",TextSel()),
            ("tfidf",TfidfVectorizer(ngram_range=(1,2),max_features=8000,
                                     sublinear_tf=True,min_df=3,max_df=0.85))])),
        ("meta", DynamicMeta()),
        ("cat", CatEnc()),
    ]))]
    steps.append(("clf", lgb.LGBMClassifier(
        n_estimators=150, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=1, verbose=-1,
        subsample=0.85, colsample_bytree=0.8, class_weight="balanced")))
    return Pipeline(steps)

def make_pipe_no_tfidf(meta_cols):
    keep = set(meta_cols)
    class DynamicMeta(BaseEstimator,TransformerMixin):
        def fit(self,X,y=None): return self
        def transform(self,X):
            return X[[c for c in ALL_META if c in keep]].values.astype(float)
    steps = [("feat", FeatureUnion([
        ("meta", DynamicMeta()),
        ("cat", CatEnc()),
    ]))]
    steps.append(("clf", lgb.LGBMClassifier(
        n_estimators=150, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=1, verbose=-1,
        subsample=0.85, colsample_bytree=0.8, class_weight="balanced")))
    return Pipeline(steps)

def make_pipe_no_cats(meta_cols):
    keep = set(meta_cols)
    class DynamicMeta(BaseEstimator,TransformerMixin):
        def fit(self,X,y=None): return self
        def transform(self,X):
            return X[[c for c in ALL_META if c in keep]].values.astype(float)
    steps = [("feat", FeatureUnion([
        ("txt", Pipeline([("sel",TextSel()),
            ("tfidf",TfidfVectorizer(ngram_range=(1,2),max_features=8000,
                                     sublinear_tf=True,min_df=3,max_df=0.85))])),
        ("meta", DynamicMeta()),
    ]))]
    steps.append(("clf", lgb.LGBMClassifier(
        n_estimators=150, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=1, verbose=-1,
        subsample=0.85, colsample_bytree=0.8, class_weight="balanced")))
    return Pipeline(steps)

def make_pipe_tfidf_only():
    steps = [("feat", FeatureUnion([
        ("txt", Pipeline([("sel",TextSel()),
            ("tfidf",TfidfVectorizer(ngram_range=(1,2),max_features=8000,
                                     sublinear_tf=True,min_df=3,max_df=0.85))])),
    ]))]
    steps.append(("clf", lgb.LGBMClassifier(
        n_estimators=150, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=1, verbose=-1,
        subsample=0.85, colsample_bytree=0.8, class_weight="balanced")))
    return Pipeline(steps)

def eval_pipe(pipe, X, y, cv, label):
    y_pred = cross_val_predict(pipe, X, y, cv=cv, n_jobs=1, method="predict")
    y_proba = cross_val_predict(pipe, X, y, cv=cv, n_jobs=1, method="predict_proba")[:,1]
    return {
        "config": label,
        "roc_auc": round(roc_auc_score(y, y_proba), 4),
        "f1": round(f1_score(y, y_pred), 4),
        "precision": round(precision_score(y, y_pred), 4),
        "recall": round(recall_score(y, y_pred), 4),
    }

if __name__ == "__main__":
    print("Building dataset...", flush=True)
    df = build_df()
    y = df["viral"].values
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)  # 3-fold for speed
    print(f"{len(df)} posts, viral rate={y.mean():.1%}", flush=True)

    results = []

    # ── 1. Full model (baseline) ──
    print("\n--- Full model (all features) ---", flush=True)
    r = eval_pipe(make_pipe_with_meta(ALL_META), df, y, cv, "ALL (baseline)")
    results.append(r)
    print(f"  ROC-AUC={r['roc_auc']}  F1={r['f1']}", flush=True)

    # ── 2. Ablate feature blocks ──
    print("\n--- Removing major feature blocks ---", flush=True)
    for name, cols in [("TF-IDF (text only)", None),
                        ("Categories", None),
                        ("All metadata", None)]:
        pass  # handled below

    # TF-IDF only (no metadata, no cats)
    r = eval_pipe(make_pipe_tfidf_only(), df, y, cv, "TF-IDF only")
    results.append(r)
    print(f"  TF-IDF only:          ROC-AUC={r['roc_auc']}  F1={r['f1']}", flush=True)

    # Metadata + cats only (no TF-IDF)
    r = eval_pipe(make_pipe_no_tfidf(ALL_META), df, y, cv, "meta+cats only (no TF-IDF)")
    results.append(r)
    print(f"  meta+cats only:       ROC-AUC={r['roc_auc']}  F1={r['f1']}", flush=True)

    # TF-IDF + cats (no metadata)
    r = eval_pipe(make_pipe_no_cats(ALL_META), df, y, cv, "TF-IDF+cats (no meta)")
    results.append(r)
    print(f"  TF-IDF+cats (no meta): ROC-AUC={r['roc_auc']}  F1={r['f1']}", flush=True)

    # ── 3. Remove individual metadata groups ──
    print("\n--- Removing metadata groups ---", flush=True)
    for name, cols in GROUPS.items():
        if name == "ALL": continue
        remaining = [c for c in ALL_META if c not in cols]
        r = eval_pipe(make_pipe_with_meta(remaining), df, y, cv, f"wo/{name}")
        results.append(r)
        print(f"  remove {name:<20} ROC-AUC={r['roc_auc']}  F1={r['f1']}", flush=True)

    # ── 4. Summary ──
    print("\n" + "="*60)
    print("ABLATION SUMMARY")
    print("="*60)

    baseline_auc = [r for r in results if r['config'] == 'ALL (baseline)'][0]['roc_auc']
    baseline_f1 = [r for r in results if r['config'] == 'ALL (baseline)'][0]['f1']

    rows = []
    for r in results:
        d_auc = round((r['roc_auc'] - baseline_auc) * 100, 2)
        d_f1 = round((r['f1'] - baseline_f1) * 100, 2)
        rows.append({**r, "ΔAUC": d_auc, "ΔF1": d_f1})

    df_r = pd.DataFrame(rows).sort_values("roc_auc", ascending=False)

    print(f"\nBaseline: ROC-AUC={baseline_auc}, F1={baseline_f1}")
    print()
    for _, r in df_r.iterrows():
        arrow_auc = "⬇" if r['ΔAUC'] < 0 else ("⬆" if r['ΔAUC'] > 0 else " ")
        arrow_f1 = "⬇" if r['ΔF1'] < 0 else ("⬆" if r['ΔF1'] > 0 else " ")
        print(f"  {r['config']:<30}  AUC={r['roc_auc']:.4f} {arrow_auc}{r['ΔAUC']:+.2f}  "
              f"F1={r['f1']:.4f} {arrow_f1}{r['ΔF1']:+.2f}")

    # Most impactful removals
    print("\n--- Biggest drops from removing metadata groups ---")
    meta_abl = [r for r in results if r['config'].startswith('wo/')]
    meta_abl.sort(key=lambda x: x['roc_auc'])
    for r in meta_abl[:5]:
        name = r['config'][3:]  # strip "wo/"
        d_auc = round((r['roc_auc'] - baseline_auc)*100, 2)
        impact = "HIGH" if abs(d_auc) >= 1.0 else ("MED" if abs(d_auc) >= 0.3 else "LOW")
        print(f"    {name:<20}  ΔAUC={d_auc:+.2f}  [{impact}]")