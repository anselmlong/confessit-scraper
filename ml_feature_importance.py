"""Quick LightGBM feature importance — trains once on all data.
Outputs metadata + category importance after controlling for TF-IDF text.
"""
import warnings, re, sqlite3, json
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.base import BaseEstimator, TransformerMixin
import lightgbm as lgb

warnings.filterwarnings("ignore")
DB_PATH = Path(__file__).parent / "data" / "messages.db"

_TEMPLATE_MARKERS = ["Click here","NUSConfessIT_bot","👇 Comment **below** anonymously",
    "😆 Send an **anonymous message**","Send an **anonymous message**",
    "PM THIS","PM Confessor","post a confession","post **YOUR OWN** confession",
    "post your own anonymous"]
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
    for (pid,date,rb,rt,fw,rc,rpc) in rows:
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
        recs.append({
            "txt": conf, "cat": cat,
            "hour": h, "dow": dw, "month": mo,
            "wc": len(w), "cc": len(conf),
            "lc": conf.count("\n")+1,
        })
    df = pd.DataFrame(recs)
    # Score = reactions + 2*replies + 3*forwards
    # We don't have the raw engagement in this df — let me redo this
    conn2=sqlite3.connect(DB_PATH)
    sc_rows=conn2.execute("SELECT id, reactions_count, reply_count, forwards FROM messages WHERE is_reply=0").fetchall()
    conn2.close()
    sc_map = {r[0]: r[1]*1 + r[2]*2 + r[3]*3 for r in sc_rows}
    # Match by iterating
    # Actually the build_df iterates through rows sequentially, so I need the score per row
    pass

# Simpler approach: rebuild with scores included
def build_df_with_scores():
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("""SELECT id,date,COALESCE(NULLIF(content,''),NULLIF(text,'')) AS rb,
           text,forwards,reactions_count,reply_count FROM messages WHERE is_reply=0
           AND COALESCE(NULLIF(content,''),NULLIF(text,'')) IS NOT NULL""").fetchall()
    conn.close()
    sia=SentimentIntensityAnalyzer()
    recs=[]
    for (pid,date,rb,rt,fw,rc,rpc) in rows:
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
        score = (rc or 0)*1 + (rpc or 0)*2 + (fw or 0)*3
        recs.append({
            "txt": conf, "cat": cat,
            "hour": h, "dow": dw, "month": mo,
            "wc": len(w), "cc": len(conf),
            "lc": conf.count("\n")+1,
            "score": score,
        })
    df = pd.DataFrame(recs)
    th = df["score"].quantile(0.75)
    df["viral"] = (df["score"] >= th).astype(int)
    return df

print("Building dataset...", flush=True)
df = build_df_with_scores()
y = df["viral"].values
print(f"{len(df)} posts, viral rate={y.mean():.1%}", flush=True)

META_COLS = ["hour","dow","month","wc","cc","lc"]

class TextSel(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X["txt"].fillna("").values
class CatEnc(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None):
        self.cats_=sorted(X["cat"].unique()); return self
    def transform(self,X):
        a=np.zeros((len(X),len(self.cats_)),dtype=float)
        for i,c in enumerate(X["cat"]):
            if c in self.cats_:
                a[i,self.cats_.index(c)]=1.0
        return a

class MetaSel(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X[META_COLS].values.astype(float)

pipe = Pipeline([
    ("feat", FeatureUnion([
        ("txt", Pipeline([("sel",TextSel()),
            ("tfidf",TfidfVectorizer(ngram_range=(1,2),max_features=8000,
                                     sublinear_tf=True,min_df=3,max_df=0.85))])),
        ("meta", MetaSel()),
        ("cat", CatEnc()),
    ])),
    ("clf", lgb.LGBMClassifier(
        n_estimators=150, max_depth=6, learning_rate=0.1,
        random_state=42, n_jobs=-1, verbose=-1,
        subsample=0.85, colsample_bytree=0.8, class_weight="balanced")),
])

print("Training on all data...", flush=True)
pipe.fit(df, y)
clf = pipe.named_steps["clf"]
feat_union = pipe.named_steps["feat"]

tfidf = feat_union.transformer_list[0][1].named_steps["tfidf"]
tfidf_names = tfidf.get_feature_names_out()
cats = feat_union.transformer_list[2][1].cats_

importances = clf.feature_importances_
n_tfidf = len(tfidf_names)
n_meta = len(META_COLS)
n_cat = len(cats)

tfidf_imp = importances[:n_tfidf]
meta_imp = importances[n_tfidf:n_tfidf+n_meta]
cat_imp = importances[n_tfidf+n_meta:n_tfidf+n_meta+n_cat]

# Metadata feature importance
meta_ranked = sorted(zip(META_COLS, meta_imp), key=lambda x: -x[1])
total_meta = sum(meta_imp)
print(f"\nMetadata importance (total {int(total_meta)}):")
for name, imp in meta_ranked:
    pct = imp / sum(importances) * 100
    print(f"  {name:<8} {imp:>5.0f}  ({pct:.1f}% of total model)")

# Category importance
total_cat = sum(cat_imp)
print(f"\nCategory importance (total {int(total_cat)}):")
for name, imp in sorted(zip(cats, cat_imp), key=lambda x: -x[1]):
    pct = imp / sum(importances) * 100
    print(f"  {name:<15} {imp:>5.0f}  ({pct:.1f}%)")

# Top 20 TF-IDF tokens
print(f"\nTop 20 TF-IDF tokens (total {int(sum(tfidf_imp))}):")
top_tfidf_idx = np.argsort(tfidf_imp)[-20:][::-1]
for idx in top_tfidf_idx:
    pct = tfidf_imp[idx] / sum(importances) * 100
    print(f"  {tfidf_names[idx]:<25} {tfidf_imp[idx]:>5.0f}  ({pct:.2f}%)")

# Feature group breakdown
print(f"\n=== FEATURE GROUP IMPORTANCE ===")
print(f"  TF-IDF (text tokens):     {sum(tfidf_imp):>5.0f}  ({sum(tfidf_imp)/sum(importances)*100:.1f}%)")
print(f"  Metadata (6 features):    {sum(meta_imp):>5.0f}  ({sum(meta_imp)/sum(importances)*100:.1f}%)")  
print(f"  Category (one-hot):       {sum(cat_imp):>5.0f}  ({sum(cat_imp)/sum(importances)*100:.1f}%)")
print(f"  Total:                    {sum(importances):>5.0f}")

# Output as JSON for the frontend
result = {
    "metadata_importance": [{"feature": name, "importance": int(imp)} for name, imp in meta_ranked],
    "category_importance": [{"category": name, "importance": int(imp)} for name, imp in sorted(zip(cats, cat_imp), key=lambda x: -x[1])],
    "top_tfidf_tokens": [{"token": tfidf_names[idx], "importance": int(tfidf_imp[idx])} for idx in top_tfidf_idx],
    "group_breakdown": {
        "tfidf": {"importance": int(sum(tfidf_imp)), "pct": round(sum(tfidf_imp)/sum(importances)*100, 1)},
        "metadata": {"importance": int(sum(meta_imp)), "pct": round(sum(meta_imp)/sum(importances)*100, 1)},
        "category": {"importance": int(sum(cat_imp)), "pct": round(sum(cat_imp)/sum(importances)*100, 1)},
    }
}

out_path = Path(__file__).parent / "data" / "ml_results" / "feature_importance.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(result, indent=2))
print(f"\nSaved to {out_path}")
