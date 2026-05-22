#!/usr/bin/env python3
"""Quick correlation analysis + v5 run with new features."""

import warnings, re, sqlite3
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score, confusion_matrix
import lightgbm as lgb

warnings.filterwarnings("ignore")
DB_PATH = Path(__file__).parent / "data" / "messages.db"

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

        # ── New features ──
        txt_lower = conf.lower()

        # Relationship keyword density
        rel_kws = ["bf","gf","boyfriend","girlfriend","crush","cheat","cheating",
                    "ex","relationship","dating","date","love","breakup","broke up",
                    "husband","wife","partner"]
        rel_count = sum(txt_lower.count(k) for k in rel_kws)

        # Rhetorical hooks
        hooks = ["am i the only one","hot take","unpopular opinion","am i wrong",
                  "does anyone else","tell me i'm not","is it just me","cmv"]
        hook_count = sum(txt_lower.count(k) for k in hooks)

        # Call to action
        cta = ["react","vote","what do you think","comment","thoughts?","opinions?",
               "what would you","what should i","agree","disagree"]
        cta_count = sum(txt_lower.count(k) for k in cta)

        # Curse words
        curses = ["fuck","shit","damn","bitch","ass","wtf","stfu","hell",
                   "suck","crap","piss","dick"]
        curse_count = sum(txt_lower.count(k) for k in curses)

        # Academic stress
        acad = ["exam","exams","gpa","cap","fail","failed","grade","deadline",
                "project","assignment","study","studying","lecture","tutorial","quiz",
                "midterm","final","semester","mods","module","homework","stress"]
        acad_count = sum(txt_lower.count(k) for k in acad)

        # Hour bins
        if h < 6: hour_bin = 0  # night
        elif h < 12: hour_bin = 1  # morning
        elif h < 14: hour_bin = 2  # lunch
        elif h < 18: hour_bin = 3  # afternoon
        elif h < 22: hour_bin = 4  # evening
        else: hour_bin = 5  # late

        # Specific days
        is_monday = int(dw == 0)
        is_friday = int(dw == 4)

        # Post position — approximate: earlier posts in the day get more eyes
        # We'll use this as a derived feature from the date

        # Ellipsis count
        ellipsis_count = conf.count("...") + conf.count("…")

        # All-caps words
        allcaps_words = sum(1 for word in w if len(word) > 2 and word.isupper())

        # Length bins
        wc = len(w)
        if wc < 20: len_bin = 0  # short
        elif wc < 80: len_bin = 1  # medium
        else: len_bin = 2  # long

        recs.append({
            "txt": conf, "cat": cat,
            # Kept: time features (strong signal)
            "hour": h, "dow": dw, "month": mo,
            "in": int(h<6 or h>=22), "iw": int(dw>=5),
            # Kept: writing style (moderate signal)
            "emc": sum(1 for c in conf if ord(c)>0x1F300),
            "hq": int("?" in conf),
            # Kept: text stats
            "wc": wc, "cc": len(conf), "lc": conf.count("\n")+1,
            # NEW features
            "rel_density": rel_count / max(len(w), 1),
            "hook_count": hook_count,
            "cta_count": cta_count,
            "curse_count": curse_count,
            "acad_density": acad_count / max(len(w), 1),
            "hour_bin": hour_bin,
            "is_monday": is_monday,
            "is_friday": is_friday,
            "ellipsis_count": ellipsis_count,
            "allcaps_count": allcaps_words,
            "len_bin": len_bin,
            # Target
            "rc": rc or 0, "rpc": rpc or 0, "fw": fw or 0,
            "vs": round((rc*1 + rpc*2 + fw*3) / 6, 2),
        })
    df = pd.DataFrame(recs)
    th = df["vs"].quantile(0.75)
    df["viral"] = (df["vs"] >= th).astype(int)
    return df

# ─── Features ────────────────────────────────────────────────────────────────

# CUT from v4: sentiment_pos/neg/neu/compound, sentiment_abs, flesch,
#   caps_ratio, punct_ratio, avg_word_len, unique_word_ratio,
#   url_count, is_exam, is_recess, has_media, exclamation_count

# KEPT from v4: hour, dow, month, is_night, is_weekend,
#   emoji_count, has_question, word_count, char_count, line_count

# NEW: rel_density, hook_count, cta_count, curse_count, acad_density,
#   hour_bin, is_monday, is_friday, ellipsis_count, allcaps_count, len_bin

META_COLS = [
    # Kept from v4
    "hour","dow","month","in","iw",
    "emc","hq",
    "wc","cc","lc",
    # New
    "rel_density","hook_count","cta_count","curse_count","acad_density",
    "hour_bin","is_monday","is_friday","ellipsis_count","allcaps_count","len_bin",
]

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

def make_pipe():
    return Pipeline([
        ("feat", FeatureUnion([
            ("txt", Pipeline([("sel",TextSel()),
                ("tfidf",TfidfVectorizer(ngram_range=(1,2),max_features=8000,
                                         sublinear_tf=True,min_df=3,max_df=0.85))])),
            ("meta", Pipeline([("sel2",TextSel()),  # dummy, will override below
            ])),
            ("cat", CatEnc()),
        ])),
        ("clf", lgb.LGBMClassifier(
            n_estimators=150, max_depth=6, learning_rate=0.1,
            random_state=42, n_jobs=1, verbose=-1,
            subsample=0.85, colsample_bytree=0.8, class_weight="balanced")),
    ])

class MetaExt(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None): return self
    def transform(self,X): return X[META_COLS].values.astype(float)

def make_pipe_v5():
    return Pipeline([
        ("feat", FeatureUnion([
            ("txt", Pipeline([("sel",TextSel()),
                ("tfidf",TfidfVectorizer(ngram_range=(1,2),max_features=8000,
                                         sublinear_tf=True,min_df=3,max_df=0.85))])),
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
    print("Building dataset (v5)...", flush=True)
    df = build_df()
    y = df["viral"].values
    print(f"{len(df)} posts, viral rate={y.mean():.1%}", flush=True)

    # ── 1. Correlation analysis ──
    print("\n=== CORRELATION WITH VIRAL (all features) ===")
    numeric_cols = [c for c in META_COLS if c not in ("cat",)]
    corrs = []
    for c in numeric_cols:
        corr = df[c].corr(df["viral"])
        corrs.append((c, corr, abs(corr)))
    corrs.sort(key=lambda x: -x[2])
    print(f"{'Feature':<22} {'Corr':>8} {'Strength':<10}")
    print("-" * 42)
    for name, corr, _ in corrs:
        s = "strong" if abs(corr)>0.15 else ("moderate" if abs(corr)>0.07 else "weak")
        arrow = "🟢" if corr>0 else "🔴"
        print(f"  {arrow} {name:<20} {corr:>+8.3f}  {s}")

    # ── 2. Run v5 ──
    print("\n=== TRAINING V5 ===", flush=True)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    pipe = make_pipe_v5()

    y_pred = cross_val_predict(pipe, df, y, cv=cv, n_jobs=1, method="predict")
    y_proba = cross_val_predict(pipe, df, y, cv=cv, n_jobs=1, method="predict_proba")[:,1]

    precision = precision_score(y, y_pred)
    recall = recall_score(y, y_pred)
    f1 = f1_score(y, y_pred)
    roc_auc = roc_auc_score(y, y_proba)
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()

    print(f"\n--- v5 Performance ---")
    print(f"  ROC-AUC:  {roc_auc:.3f}")
    print(f"  F1:       {f1:.3f}")
    print(f"  Precision:{precision:.3f}")
    print(f"  Recall:   {recall:.3f}")
    print(f"  TN={tn} FP={fp} FN={fn} TP={tp}")
    print(f"  Accuracy: {(tn+tp)/(tn+fp+fn+tp):.3f}")

    # ── 3. Feature importance ──
    pipe.fit(df, y)
    clf = pipe.named_steps["clf"]
    feat_union = pipe.named_steps["feat"]
    tfidf_names = feat_union.transformer_list[0][1].named_steps["tfidf"].get_feature_names_out()
    cats = feat_union.transformer_list[2][1].cats_
    importances = clf.feature_importances_
    n_tfidf = len(tfidf_names)
    n_meta = len(META_COLS)
    n_cat = len(cats)

    tfidf_imp = importances[:n_tfidf]
    meta_imp = importances[n_tfidf:n_tfidf+n_meta]
    cat_imp = importances[n_tfidf+n_meta:n_tfidf+n_meta+n_cat]

    print("\n--- Metadata feature importance ---")
    meta_ranked = sorted(zip(META_COLS, meta_imp), key=lambda x: -x[1])
    max_imp = max(m[1] for m in meta_ranked) if meta_ranked else 1
    for name, imp in meta_ranked:
        bar = "█" * int(imp / max_imp * 25) if max_imp else ""
        print(f"  {name:<20} {imp:>5.0f}  {bar}")

    print("\n--- Category importance ---")
    for name, imp in sorted(zip(cats, cat_imp), key=lambda x: -x[1]):
        print(f"  {name:<15} {imp:>5.0f}")

    # ── 4. Compare ──
    print(f"\n=== COMPARISON ===")
    print(f"  v3 (leaky):          AUC=0.799  F1=0.529")
    print(f"  v4 (clean baseline): AUC=0.774  F1=0.545")
    print(f"  v5 (new features):   AUC={roc_auc:.3f}  F1={f1:.3f}")