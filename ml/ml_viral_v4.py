#!/usr/bin/env python3
"""
v4: Binary viral classifier with cleaned training data.

Changes from v3:
  1. Excludes 183 Helix House suicide posts (sensitive anomaly)
  2. Removes reply_per_word from features (target leakage)
  3. Composite target: virality_score = (reactions×1 + replies×2 + forwards×3) / 6
  4. Binary label: top 25% of virality_score = viral
"""

import sys, warnings, re, sqlite3
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
from sklearn.metrics import (classification_report, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
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

HELIX_KEYWORDS = ["helix", "Helix", "helix house", "Helix House"]

def is_helix_post(text, raw_body):
    combined = f"{text or ''} {raw_body or ''}"
    for kw in HELIX_KEYWORDS:
        if kw in combined:
            return True
    return False

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
    excluded_helix = 0
    for (pid,date,raw_body,raw_text,forwards,reactions,rcount) in rows:
        conf=extract_confession_text(raw_body)
        if not conf or len(conf)<10: continue
        if sum(c.isalpha() for c in conf)/max(len(conf),1)<0.2: continue

        # Exclude Helix House posts
        if is_helix_post(raw_text, raw_body):
            excluded_helix += 1
            continue

        sent=sia.polarity_scores(conf)
        words=conf.split()
        hour=dow=month=-1
        try: dt=datetime.fromisoformat(date); hour, dow, month = dt.hour, dt.weekday(), dt.month
        except: pass
        m=re.search(r"\*\*#(\w+)\*\*",raw_text or raw_body)
        cat=m.group(1).lower() if m else "unknown"

        # Composite virality score
        v_score = (reactions*1 + rcount*2 + forwards*3) / 6

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
            # NO reply_per_word — removed to prevent target leakage
            "reactions_count":reactions or 0,
            "reply_count":rcount or 0,
            "forwards_count":forwards or 0,
            "virality_score":round(v_score, 2),
        })

    df = pd.DataFrame(recs)
    print(f"Built dataset: {len(df)} posts ({excluded_helix} Helix House excluded)", flush=True)
    return df

# ─── Pipeline ────────────────────────────────────────────────────────────────

# NOTE: reply_per_word deliberately excluded — would require knowing reply_count
# before the post goes up (target leakage)
META_COLS = ["hour","day_of_week","month","word_count","char_count","avg_word_len",
    "has_question","exclamation_count","caps_ratio","emoji_count",
    "sentiment_pos","sentiment_neg","sentiment_neu","sentiment_compound",
    "is_night","is_weekend","is_exam","is_recess",
    "unique_word_ratio","punct_ratio","url_count","line_count",
    "flesch","sentiment_abs","has_media"]

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

def build_pipeline():
    return Pipeline([
        ("feat", FeatureUnion([
            ("txt", Pipeline([("sel",TextSel()),("tfidf",TfidfVectorizer(**TFIDF_KW))])),
            ("meta", MetaExt()),
            ("cat", CatEnc()),
        ])),
        ("clf", lgb.LGBMClassifier(
            n_estimators=150, max_depth=6, learning_rate=0.1,
            random_state=42, n_jobs=1, verbose=-1,
            subsample=0.85, colsample_bytree=0.8,
            class_weight="balanced",
        )),
    ])

# ─── Analysis ────────────────────────────────────────────────────────────────

def analyze_feature_importance(pipeline, meta_cols, cat_encoder):
    feat_union = pipeline.named_steps["feat"]
    clf = pipeline.named_steps["clf"]
    tfidf_pipe = feat_union.transformer_list[0][1]
    tfidf_names = tfidf_pipe.named_steps["tfidf"].get_feature_names_out()
    cats = cat_encoder.cats_

    importances = clf.feature_importances_
    n_tfidf = len(tfidf_names)
    n_meta = len(meta_cols)
    n_cat = len(cats)

    tfidf_imp = importances[:n_tfidf]
    meta_imp = importances[n_tfidf:n_tfidf+n_meta]
    cat_imp = importances[n_tfidf+n_meta:n_tfidf+n_meta+n_cat]

    print("\n  Top bigrams/tokens driving viral predictions:")
    top_tfidf_idx = np.argsort(tfidf_imp)[-30:][::-1]
    for i in top_tfidf_idx:
        if tfidf_imp[i] > 10:
            print(f"    {tfidf_names[i]:>30}  {tfidf_imp[i]:>6.0f}")

    print("\n  Metadata feature importance:")
    meta_ranked = sorted(zip(meta_cols, meta_imp), key=lambda x: -x[1])
    max_imp = max(m[1] for m in meta_ranked) if meta_ranked else 1
    for name, imp in meta_ranked:
        bar = "█" * int(imp / max_imp * 28) if max_imp > 0 else ""
        print(f"    {name:<22} {imp:>6.0f}  {bar}")

    print("\n  Category importance:")
    for name, imp in sorted(zip(cats, cat_imp), key=lambda x: -x[1]):
        print(f"    {name:<15} {imp:>6.0f}")


def analyze_viral_patterns(df, threshold):
    viral = df[df["viral"] == 1]
    nonviral = df[df["viral"] == 0]

    print(f"\n  Viral ({len(viral)}): score range [{viral['virality_score'].min():.1f}–{viral['virality_score'].max():.1f}], "
          f"median={viral['virality_score'].median():.1f}")
    print(f"  Non-viral ({len(nonviral)}): score range [{nonviral['virality_score'].min():.1f}–{nonviral['virality_score'].max():.1f}], "
          f"median={nonviral['virality_score'].median():.1f}")

    features = [
        ("word_count", "Word count", False),
        ("char_count", "Char count", False),
        ("sentiment_compound", "Sentiment (compound)", False),
        ("sentiment_abs", "Sentiment intensity", False),
        ("emoji_count", "Emoji count", False),
        ("caps_ratio", "Caps ratio", False),
        ("flesch", "Readability (Flesch)", False),
        ("unique_word_ratio", "Vocabulary richness", False),
        ("has_question", "Has question?", True),
        ("exclamation_count", "Exclamation count", False),
        ("avg_word_len", "Avg word length", False),
        ("punct_ratio", "Punctuation density", False),
        ("url_count", "URL count", False),
        ("line_count", "Line count", False),
        ("is_night", "Posted at night", True),
        ("is_weekend", "Posted weekend", True),
        ("is_exam", "Posted exam period", True),
        ("is_recess", "Posted recess week", True),
        ("hour", "Hour (avg)", False),
    ]

    print("\n  Feature comparison (viral vs non-viral):")
    print(f"  {'Feature':<25} {'Non-viral':<12} {'Viral':<12} {'Diff':<10}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")

    for col, label, is_binary in features:
        if is_binary:
            nv_pct = nonviral[col].mean() * 100
            v_pct = viral[col].mean() * 100
            print(f"  {label:<25} {nv_pct:>6.1f}%    {v_pct:>6.1f}%    {v_pct-nv_pct:>+5.1f}%")
        else:
            nv = nonviral[col].mean()
            v = viral[col].mean()
            pct = (v-nv)/max(abs(nv),0.001)*100
            print(f"  {label:<25} {nv:>10.2f}  {v:>10.2f}  {v-nv:>+8.2f}  ({pct:+.0f}%)")

    # Category rates on the NEW score
    print("\n  Category distribution (by new score):")
    cat_dist = df.groupby("category").agg(
        count=("virality_score", "count"),
        avg_score=("virality_score", "mean"),
        viral_rate=("viral", "mean"),
    ).sort_values("viral_rate", ascending=False)
    for cat, row in cat_dist.iterrows():
        bar = "█" * int(row["viral_rate"] * 30)
        print(f"    {cat:<15} {row['count']:>5} posts  viral rate={row['viral_rate']:.1%}  avg score={row['avg_score']:.1f}  {bar}")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building dataset (v4 — no Helix, no reply_per_word, composite score)...", flush=True)
    df = build_df()

    # Composite target
    df["virality_score"] = (df["reactions_count"]*1 + df["reply_count"]*2 + df["forwards_count"]*3) / 6

    # Binary label: top 25% by virality_score
    threshold = df["virality_score"].quantile(0.75)
    df["viral"] = (df["virality_score"] >= threshold).astype(int)
    viral_rate = df["viral"].mean()

    print(f"\nComposite score distribution:")
    print(f"  Mean: {df['virality_score'].mean():.1f}, Median: {df['virality_score'].median():.1f}")
    print(f"  Threshold for top 25% (viral): {threshold:.2f}")
    print(f"  Viral count: {df['viral'].sum()}/{len(df)} ({viral_rate:.1%})", flush=True)

    # Train
    print("\nTraining LightGBM classifier...", flush=True)
    X, y = df, df["viral"].values
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    pipe = build_pipeline()

    y_pred = cross_val_predict(pipe, X, y, cv=cv, n_jobs=1, method="predict")
    y_proba = cross_val_predict(pipe, X, y, cv=cv, n_jobs=1, method="predict_proba")[:, 1]

    # Metrics
    precision = precision_score(y, y_pred)
    recall = recall_score(y, y_pred)
    f1 = f1_score(y, y_pred)
    roc_auc = roc_auc_score(y, y_proba)
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()

    print(f"\n--- Performance (5-fold CV) ---")
    print(f"  Precision:  {precision:.3f}")
    print(f"  Recall:     {recall:.3f}")
    print(f"  F1-score:   {f1:.3f}")
    print(f"  ROC-AUC:    {roc_auc:.3f}")
    print(f"  TN={tn}  FP={fp}  FN={fn}  TP={tp}")
    print(f"  Accuracy:   {(tn+tp)/(tn+fp+fn+tp):.3f}")

    # Feature analysis
    print("\n--- Feature Analysis ---", flush=True)
    pipe.fit(X, y)
    cat_enc = pipe.named_steps["feat"].transformer_list[2][1]
    analyze_feature_importance(pipe, META_COLS, cat_enc)

    # Pattern analysis
    print("\n--- Raw Data Patterns ---", flush=True)
    analyze_viral_patterns(df, threshold)

    # Compare: v3 vs v4
    print("\n--- Comparison with v3 ---")
    print(f"  v3 (10+ reactions, with reply_per_word + Helix): ROC-AUC=0.799, F1=0.529")
    print(f"  v4 (composite score, no Helix, no reply_per_word): ROC-AUC={roc_auc:.3f}, F1={f1:.3f}")