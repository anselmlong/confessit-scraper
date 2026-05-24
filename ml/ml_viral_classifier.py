#!/usr/bin/env python3
"""Binary classification: viral (10+ reactions) vs not. Feature importance + patterns."""

import sys, warnings, re, sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import (classification_report, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score,
                             precision_recall_curve, ConfusionMatrixDisplay)
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

# ─── Pipeline ────────────────────────────────────────────────────────────────

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
            class_weight="balanced",  # important: only 25% are viral
        )),
    ])

# ─── Analysis ────────────────────────────────────────────────────────────────

def analyze_feature_importance(pipeline, meta_cols, cat_encoder, n_top=30):
    """Extract top TF-IDF tokens + metadata features."""
    # Get the feature union and classifier
    feat_union = pipeline.named_steps["feat"]
    clf = pipeline.named_steps["clf"]

    # Get TF-IDF feature names
    tfidf_pipe = feat_union.transformer_list[0][1]
    tfidf_vec = tfidf_pipe.named_steps["tfidf"]
    tfidf_names = tfidf_vec.get_feature_names_out()

    # Get category names
    cats = cat_encoder.cats_

    # Get importances from LightGBM
    importances = clf.feature_importances_

    # Split: TF-IDF features, then meta features, then cat features
    n_tfidf = len(tfidf_names)
    n_meta = len(meta_cols)
    n_cat = len(cats)

    tfidf_imp = importances[:n_tfidf]
    meta_imp = importances[n_tfidf:n_tfidf+n_meta]
    cat_imp = importances[n_tfidf+n_meta:n_tfidf+n_meta+n_cat]

    # Top TF-IDF tokens
    top_tfidf_idx = np.argsort(tfidf_imp)[-n_top:][::-1]
    print("\n  Top bigrams/tokens driving viral predictions:")
    for i in top_tfidf_idx:
        print(f"    {tfidf_names[i]:>30}  {tfidf_imp[i]:>6.0f}")

    # Meta features ranked
    print("\n  Metadata feature importance:")
    meta_ranked = sorted(zip(meta_cols, meta_imp), key=lambda x: -x[1])
    for name, imp in meta_ranked:
        bar = "█" * int(imp / max(meta_imp) * 30) if max(meta_imp) > 0 else ""
        print(f"    {name:<22} {imp:>6.0f}  {bar}")

    # Category importance
    print("\n  Category importance:")
    for name, imp in sorted(zip(cats, cat_imp), key=lambda x: -x[1]):
        print(f"    {name:<15} {imp:>6.0f}")


def analyze_viral_patterns(df):
    """Statistical comparison of viral vs non-viral posts."""
    viral = df[df["reactions_count"] >= 10]
    nonviral = df[df["reactions_count"] < 10]

    print(f"\n  Viral ({len(viral)}): mean={viral['reactions_count'].mean():.1f}, "
          f"median={viral['reactions_count'].median():.0f}")
    print(f"  Non-viral ({len(nonviral)}): mean={nonviral['reactions_count'].mean():.1f}, "
          f"median={nonviral['reactions_count'].median():.0f}")

    meta_analysis = [
        ("word_count", "Word count"),
        ("char_count", "Char count"),
        ("sentiment_compound", "Sentiment (compound)"),
        ("sentiment_abs", "Sentiment intensity"),
        ("emoji_count", "Emoji count"),
        ("caps_ratio", "Caps ratio"),
        ("flesch", "Readability (Flesch)"),
        ("unique_word_ratio", "Vocabulary richness"),
        ("has_question", "Has question? (%)"),
        ("exclamation_count", "Exclamation count"),
        ("avg_word_len", "Avg word length"),
        ("punct_ratio", "Punctuation density"),
        ("url_count", "URL count"),
        ("line_count", "Line count"),
        ("is_night", "Posted at night (%)"),
        ("is_weekend", "Posted weekend (%)"),
        ("is_exam", "Posted exam period (%)"),
        ("is_recess", "Posted recess week (%)"),
        ("hour", "Hour (avg)"),
        ("reply_per_word", "Reply density"),
    ]

    print("\n  Feature comparison (viral vs non-viral):")
    print(f"  {'Feature':<25} {'Non-viral':<12} {'Viral':<12} {'Diff':<10} {'Direction':<20}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10} {'-'*20}")

    for col, label in meta_analysis:
        if col in ["has_question", "is_night", "is_weekend", "is_exam", "is_recess", "has_media"]:
            # Binary — show percentages
            nv_pct = nonviral[col].mean() * 100
            v_pct = viral[col].mean() * 100
            diff = v_pct - nv_pct
            direction = "↑ viral" if diff > 0 else "↓ viral"
            print(f"  {label:<25} {nv_pct:>6.1f}%    {v_pct:>6.1f}%    {diff:>+5.1f}%   {direction}")
        else:
            nv_mean = nonviral[col].mean()
            v_mean = viral[col].mean()
            diff = v_mean - nv_mean
            pct_change = (diff / max(abs(nv_mean), 0.001)) * 100
            direction = "↑ viral" if diff > 0 else "↓ viral"
            print(f"  {label:<25} {nv_mean:>10.2f}  {v_mean:>10.2f}  {diff:>+8.2f}  {direction} ({pct_change:+.0f}%)")

    # Category distribution
    print("\n  Category distribution:")
    cat_dist = df.groupby("category")["reactions_count"].agg(["count", "mean", lambda x: (x >= 10).mean()])
    cat_dist.columns = ["count", "avg_reactions", "viral_rate"]
    cat_dist = cat_dist.sort_values("viral_rate", ascending=False)
    for cat, row in cat_dist.iterrows():
        bar = "█" * int(row["viral_rate"] * 30)
        print(f"    {cat:<15} {row['count']:>5} posts  viral rate={row['viral_rate']:.1%}  {bar}")

    # Time patterns
    print("\n  Hourly viral rate:")
    hourly = df.groupby("hour")["reactions_count"].apply(lambda x: (x >= 10).mean())
    for h in range(24):
        if h in hourly.index:
            v = hourly[h]
            bar = "█" * int(v * 30)
            print(f"    {h:02d}:00  {v:.1%}  {bar}")

    # Top categories with text examples
    print("\n  Top 5 most viral posts:")
    top = df.nlargest(5, "reactions_count")
    for _, row in top.iterrows():
        txt = row["confession_text"][:120].replace("\n", " ")
        print(f"    [{row['reactions_count']} reactions] {txt}...")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building dataset...", flush=True)
    df = build_df()
    print(f"{len(df)} posts", flush=True)

    # Binary label: 10+ = viral
    df["viral"] = (df["reactions_count"] >= 10).astype(int)
    viral_rate = df["viral"].mean()
    print(f"Viral threshold: 10+ reactions")
    print(f"Viral rate: {viral_rate:.1%} ({df['viral'].sum()}/{len(df)})", flush=True)

    # Build and train
    print("\nTraining LightGBM classifier...", flush=True)
    X = df
    y = df["viral"].values
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    pipe = build_pipeline()

    # Cross-validated predictions
    y_pred = cross_val_predict(pipe, X, y, cv=cv, n_jobs=1, method="predict")
    y_proba = cross_val_predict(pipe, X, y, cv=cv, n_jobs=1, method="predict_proba")[:, 1]

    # Metrics
    precision = precision_score(y, y_pred)
    recall = recall_score(y, y_pred)
    f1 = f1_score(y, y_pred)
    roc_auc = roc_auc_score(y, y_proba)

    print(f"\n--- Performance (5-fold CV) ---")
    print(f"  Precision:  {precision:.3f}  (of posts flagged viral, how many actually were)")
    print(f"  Recall:     {recall:.3f}  (of actual viral posts, how many caught)")
    print(f"  F1-score:   {f1:.3f}")
    print(f"  ROC-AUC:    {roc_auc:.3f}")
    print()
    print(f"  Confusion matrix (raw counts):")
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
    print(f"    TN={tn}  FP={fp}")
    print(f"    FN={fn}  TP={tp}")
    print(f"    Accuracy:  {(tn+tp)/(tn+fp+fn+tp):.3f}")

    # Train one full model on all data for feature importance
    print("\n--- Feature Analysis ---", flush=True)
    pipe.fit(X, y)
    cat_enc = pipe.named_steps["feat"].transformer_list[2][1]
    analyze_feature_importance(pipe, META_COLS, cat_enc)

    # Statistical pattern analysis (same data, not from model)
    print("\n--- Raw Data Patterns ---", flush=True)
    analyze_viral_patterns(df)