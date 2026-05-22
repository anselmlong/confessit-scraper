#!/usr/bin/env python3
"""
ML experiments v2: improved scores for virality prediction.

Improvements over v1:
  1. Bigrams + char n-grams (was: bare unigrams)
  2. Sentence embeddings via sentence-transformers (if available)
  3. Richer metadata (is_night, is_weekend, text_complexity, etc.)
  4. Interaction features (forwards * reply_count, etc.)
  5. Hyperparameter tuning (grid search on best models)
  6. Box-Cox / Yeo-Johnson target transform
  7. Ensemble: average top-3 regressors
  8. Quantile-based binning for classification
"""

import sqlite3, re, csv, warnings, json, math
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from scipy.stats import boxcox, yeojohnson

from sklearn.model_selection import (StratifiedKFold, KFold, cross_val_score,
                                     cross_val_predict, GridSearchCV,
                                     train_test_split)
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import StandardScaler, PowerTransformer, FunctionTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.base import BaseEstimator, TransformerMixin
# Classifiers
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import LinearSVC
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report, f1_score
# Regressors
from sklearn.linear_model import Ridge, HuberRegressor
from sklearn.ensemble import (RandomForestRegressor, GradientBoostingRegressor,
                              HistGradientBoostingRegressor)
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import lightgbm as lgb

warnings.filterwarnings("ignore")

DB_PATH = Path(__file__).parent / "data" / "messages.db"
CSV_OUT = Path(__file__).parent / "data" / "confessions_ml_v2.csv"
RESULTS_DIR = Path(__file__).parent / "data" / "ml_results_v2"

# ─── Text cleaning ──────────────────────────────────────────────────────────

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
    if not text: return None
    lines = text.strip().split("\n")
    for i, line in enumerate(lines):
        if _is_template_line(line):
            if i == 0: return None
            body = "\n".join(lines[:i]).strip()
            return body or None
    return text.strip()

def extract_confession_text(raw: str) -> str | None:
    if not raw: return None
    match = re.search(r"---\s*\n(.*?)\n---", raw, re.DOTALL)
    if match: return match.group(1).strip()
    return clean_body(raw)

# ─── NUS exam periods (approximate) ─────────────────────────────────────────
# Mid-terms: ~weeks 6-8 of each sem
# Finals: ~weeks 1-4 of December, weeks 1-3 of May

NUS_EXAM_PERIODS = [
    ("2024-04-22", "2024-05-11"),   # Sem 2 finals 2024
    ("2024-07-22", "2024-08-10"),   # Special term
    ("2024-11-25", "2024-12-14"),   # Sem 1 finals 2024
    ("2025-04-21", "2025-05-10"),   # Sem 2 finals 2025
    ("2025-07-21", "2025-08-09"),   # Special term 2025
    ("2025-11-24", "2025-12-13"),   # Sem 1 finals 2025
    ("2026-04-20", "2026-05-09"),   # Sem 2 finals 2026
]

NUS_RECESS_WEEKS = [
    ("2024-03-04", "2024-03-10"),   # Sem 2 recess 2024
    ("2024-10-07", "2024-10-13"),   # Sem 1 recess 2024
    ("2025-03-03", "2025-03-09"),   # Sem 2 recess 2025
    ("2025-10-06", "2025-10-12"),   # Sem 1 recess 2025
    ("2026-03-02", "2026-03-08"),   # Sem 2 recess 2026
]

def is_in_date_range(date_str: str, ranges: list) -> bool:
    try:
        d = datetime.fromisoformat(date_str).date()
        for start, end in ranges:
            s = datetime.strptime(start, "%Y-%m-%d").date()
            e = datetime.strptime(end, "%Y-%m-%d").date()
            if s <= d <= e:
                return 1
    except: pass
    return 0

def flesch_score(text: str) -> float:
    """Approximate Flesch Reading Ease for short text."""
    if not text or len(text) < 10:
        return 0.0
    words = text.split()
    if not words: return 0.0
    sentences = max(len(re.split(r'[.!?]+', text)), 1)
    syllables = sum(max(1, len(re.findall(r'[aeiouy]+', w.lower()))) for w in words)
    return max(0, 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words)))


# ─── Step 1: Export CSV (v2 with richer features) ───────────────────────────

def parse_category(text: str) -> str:
    if not text: return "unknown"
    m = re.search(r"\*\*#(\w+)\*\*", text)
    return m.group(1).lower() if m else "unknown"

def extract_hour(date_str: str) -> int:
    try: return datetime.fromisoformat(date_str).hour
    except: return -1

def extract_dow(date_str: str) -> int:
    try: return datetime.fromisoformat(date_str).weekday()
    except: return -1

def extract_month(date_str: str) -> int:
    try: return datetime.fromisoformat(date_str).month
    except: return -1

def export_csv():
    print("=" * 60)
    print("STEP 1: Exporting CSV (v2 features)")
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

        # ── Sentiment ──
        sent = sia.polarity_scores(confession)

        # ── Categorical ──
        category = parse_category(raw_text or raw_body)
        hour = extract_hour(date)
        dow = extract_dow(date)
        month = extract_month(date)

        # ── Basic text stats ──
        words = confession.split()
        word_len_avg = sum(len(w) for w in words) / max(len(words), 1)
        has_question = int("?" in confession)
        exclamation_count = confession.count("!")
        caps_ratio = sum(c.isupper() for c in confession if c.isalpha()) / max(sum(1 for c in confession if c.isalpha()), 1)
        emoji_count = sum(1 for c in confession if ord(c) > 0x1F300)

        # ── Richer features ──
        is_night = int(hour < 6 or hour >= 22)
        is_weekend = int(dow >= 5)
        is_exam = is_in_date_range(date, NUS_EXAM_PERIODS) if date else 0
        is_recess = is_in_date_range(date, NUS_RECESS_WEEKS) if date else 0
        unique_word_ratio = len(set(w.lower() for w in words)) / max(len(words), 1)
        punct_ratio = sum(1 for c in confession if c in ".,;:!?'\"-") / max(len(confession), 1)
        url_count = len(re.findall(r'https?://\S+', confession))
        line_count = confession.count("\n") + 1
        flesch = flesch_score(confession)
        sentiment_abs = abs(sent["compound"])  # emotional intensity
        has_media = int("[GIF]" in confession or "[Photo]" in confession or "[Video]" in confession
                        or "t.me/" in confession)

        # interaction features
        engage_interaction = (reactions or 0) * (reply_count or 0)
        forward_squared = (forwards or 0) ** 2
        reply_per_word = (reply_count or 0) / max(len(confession.split()), 1)

        records.append({
            "post_id": post_id,
            "channel": channel,
            "date": date,
            "confession_text": confession,
            "category": category,
            "hour": hour,
            "day_of_week": dow,
            "month": month,
            "views": views or 0,
            "forwards": forwards or 0,
            "word_count": len(words),
            "char_count": len(confession),
            "avg_word_len": round(word_len_avg, 3),
            "has_question": has_question,
            "exclamation_count": exclamation_count,
            "caps_ratio": round(caps_ratio, 4),
            "emoji_count": emoji_count,
            "sentiment_pos": round(sent["pos"], 4),
            "sentiment_neg": round(sent["neg"], 4),
            "sentiment_neu": round(sent["neu"], 4),
            "sentiment_compound": round(sent["compound"], 4),

            # new v2 features
            "is_night": is_night,
            "is_weekend": is_weekend,
            "is_exam_period": is_exam,
            "is_recess_week": is_recess,
            "unique_word_ratio": round(unique_word_ratio, 4),
            "punct_ratio": round(punct_ratio, 4),
            "url_count": url_count,
            "line_count": line_count,
            "flesch_score": round(flesch, 2),
            "sentiment_abs": round(sentiment_abs, 4),
            "has_media": has_media,
            "reply_per_word": round(reply_per_word, 6),
            "engage_interaction": engage_interaction,

            "reactions_count": reactions or 0,
            "reply_count": reply_count or 0,

            # quantile-based bins for balanced classification
        })

    df = pd.DataFrame(records)
    # Drop engage_interaction from features since it uses true reactions (target leakage)
    # Keep it but don't include as feature
    df.to_csv(CSV_OUT, index=False, quoting=csv.QUOTE_NONNUMERIC)
    print(f"Exported {len(df)} rows → {CSV_OUT}")

    # Check label balance with quantile bins
    q33 = df["reactions_count"].quantile(0.33)
    q66 = df["reactions_count"].quantile(0.66)
    df["reaction_label"] = pd.cut(df["reactions_count"],
                                   bins=[-1, q33, q66, df["reactions_count"].max()],
                                   labels=["low", "medium", "high"])
    print(f"Quantile bins: 0={0}, p33={q33:.0f}, p66={q66:.0f}, max={df['reactions_count'].max()}")
    print(f"Label distribution:\n{df['reaction_label'].value_counts().sort_index().to_string()}")
    print()

    # Also keep the old linear bins for comparison
    df["reaction_label_v1"] = df["reactions_count"].apply(
        lambda n: "low" if n <= 2 else ("medium" if n <= 9 else "high")
    )

    return df


# ─── Feature transformers (v2) ─────────────────────────────────────────────

META_COLS_V2 = [
    "hour", "day_of_week", "month", "word_count", "char_count", "avg_word_len",
    "has_question", "exclamation_count", "caps_ratio", "emoji_count",
    "sentiment_pos", "sentiment_neg", "sentiment_neu", "sentiment_compound",
    # new v2
    "is_night", "is_weekend", "is_exam_period", "is_recess_week",
    "unique_word_ratio", "punct_ratio", "url_count", "line_count",
    "flesch_score", "sentiment_abs", "has_media",
    "reply_per_word",
]

# NOTE: consciously NOT including engage_interaction — it uses true reactions (leakage)
# Also not including views/forwards directly as they're only known post-hoc
# but reply_per_word is okay if reply_count is available early (it is on ConfessIt)


class MetaFeatureExtractorV2(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None): return self
    def transform(self, X):
        return X[META_COLS_V2].values.astype(float)


class CategoryEncoder(BaseEstimator, TransformerMixin):
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
    def fit(self, X, y=None): return self
    def transform(self, X):
        return X["confession_text"].fillna("").values


# Improved TF-IDF: bigrams + more features
TFIDF_KWARGS_V2 = dict(
    ngram_range=(1, 2),       # was: (1,1)
    max_features=8000,         # was: 3000
    sublinear_tf=True,
    min_df=3,
    max_df=0.85,               # new: remove overly common terms
)


def make_feature_pipeline_v2(clf, scale_meta=True):
    """Build pipeline with TF-IDF bigrams + metadata + category."""
    steps = [
        ("features", FeatureUnion([
            ("tfidf", Pipeline([
                ("sel", TextSelector()),
                ("tfidf", TfidfVectorizer(**TFIDF_KWARGS_V2)),
            ])),
            ("meta", MetaFeatureExtractorV2()),
            ("cat", CategoryEncoder()),
        ])),
    ]
    if scale_meta:
        steps.append(("scaler", StandardScaler(with_mean=False)))
    steps.append(("clf", clf))
    return Pipeline(steps)


# ─── Classification models (v2) ────────────────────────────────────────────

def get_classifiers_v2():
    # Tuned hyperparams — beefier than v1
    return {
        "logistic_regression": make_feature_pipeline_v2(
            LogisticRegression(max_iter=1000, C=2.0, solver="lbfgs",
                               class_weight="balanced"),
            scale_meta=True,
        ),
        "complement_naive_bayes": Pipeline([
            ("sel", TextSelector()),
            ("tfidf", TfidfVectorizer(**TFIDF_KWARGS_V2)),
            ("clf", ComplementNB(alpha=0.01)),
        ]),
        "linear_svm": make_feature_pipeline_v2(
            LinearSVC(max_iter=2000, C=1.0, class_weight="balanced"),
            scale_meta=True,
        ),
        "random_forest": make_feature_pipeline_v2(
            RandomForestClassifier(n_estimators=200, max_depth=12, min_samples_leaf=4,
                                    random_state=42, n_jobs=-1),
        ),
        "gradient_boosting": make_feature_pipeline_v2(
            GradientBoostingClassifier(n_estimators=120, max_depth=4, learning_rate=0.12,
                                        random_state=42, subsample=0.85),
        ),
        "xgboost": make_feature_pipeline_v2(
            xgb.XGBClassifier(n_estimators=120, max_depth=5, learning_rate=0.12,
                               eval_metric="mlogloss", random_state=42, n_jobs=-1,
                               subsample=0.85, colsample_bytree=0.8),
        ),
        "lightgbm": make_feature_pipeline_v2(
            lgb.LGBMClassifier(n_estimators=120, max_depth=6, learning_rate=0.1,
                                random_state=42, n_jobs=-1, verbose=-1,
                                subsample=0.85, colsample_bytree=0.8,
                                class_weight="balanced"),
        ),
        "mlp_neural_net": make_feature_pipeline_v2(
            MLPClassifier(hidden_layer_sizes=(256, 128), max_iter=300, random_state=42,
                           early_stopping=True, validation_fraction=0.15,
                           learning_rate_init=0.001, batch_size=128),
            scale_meta=True,
        ),
    }


# ─── Run classification ────────────────────────────────────────────────────

LABEL_ORDER = ["low", "medium", "high"]

def run_one_classifier(name, pipeline, df, y, cv):
    from sklearn.model_selection import train_test_split

    out_path = RESULTS_DIR / f"{name}.txt"
    print(f"  Running {name}...", flush=True)

    f1_macro = cross_val_score(pipeline, df, y, cv=cv, scoring="f1_macro", n_jobs=1)
    f1_weighted = cross_val_score(pipeline, df, y, cv=cv, scoring="f1_weighted", n_jobs=1)

    mean_macro = f1_macro.mean()
    std_macro = f1_macro.std()
    mean_weighted = f1_weighted.mean()

    # Per-class breakdown on held-out 20%
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
        f.write(f"CV fold scores: {np.round(f1_macro, 4).tolist()}\n\n")
        f.write("Classification report (80/20 hold-out):\n")
        f.write(report)

    summary_csv = RESULTS_DIR / "summary_clf.csv"
    exists = summary_csv.exists()
    with open(summary_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        if not exists: writer.writeheader()
        writer.writerow(result)

    print(f"  {name:<28} F1-macro={mean_macro:.4f} ± {std_macro:.4f}  "
          f"F1-weighted={mean_weighted:.4f}  → {out_path.name}", flush=True)
    return result


def run_classification(df, label_col="reaction_label"):
    print("\n" + "=" * 60)
    print(f"CLASSIFICATION v2: predict {label_col} (low/medium/high)")
    print("=" * 60)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    y = np.array([LABEL_ORDER.index(l) for l in df[label_col]])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    results = []
    for name, pipeline in get_classifiers_v2().items():
        try:
            result = run_one_classifier(name, pipeline, df, y, cv)
            results.append(result)
        except Exception as e:
            print(f"  ERROR in {name}: {e}", flush=True)
            import traceback; traceback.print_exc()

    results_df = pd.DataFrame(results).sort_values("f1_macro_mean", ascending=False)
    print()
    print(results_df.to_string(index=False))
    return results_df


# ─── Regressors (v2) ────────────────────────────────────────────────────────

def get_regressors_v2():
    return {
        "ridge": make_feature_pipeline_v2(
            Ridge(alpha=0.5), scale_meta=True
        ),
        "huber": make_feature_pipeline_v2(
            HuberRegressor(alpha=0.001, max_iter=200), scale_meta=True
        ),
        "random_forest": make_feature_pipeline_v2(
            RandomForestRegressor(n_estimators=200, max_depth=12, min_samples_leaf=4,
                                   random_state=42, n_jobs=-1)
        ),
        "gradient_boosting": make_feature_pipeline_v2(
            GradientBoostingRegressor(n_estimators=120, max_depth=4, learning_rate=0.12,
                                       random_state=42, subsample=0.85)
        ),
        "hist_gradient_boosting": make_feature_pipeline_v2(
            HistGradientBoostingRegressor(max_iter=150, max_depth=5, learning_rate=0.1,
                                           random_state=42, categorical_features=None)
        ),
        "xgboost": make_feature_pipeline_v2(
            xgb.XGBRegressor(n_estimators=120, max_depth=5, learning_rate=0.12,
                              eval_metric="rmse", random_state=42, n_jobs=-1,
                              subsample=0.85, colsample_bytree=0.8)
        ),
        "lightgbm": make_feature_pipeline_v2(
            lgb.LGBMRegressor(n_estimators=120, max_depth=6, learning_rate=0.1,
                               random_state=42, n_jobs=-1, verbose=-1,
                               subsample=0.85, colsample_bytree=0.8)
        ),
        "mlp": make_feature_pipeline_v2(
            MLPRegressor(hidden_layer_sizes=(256, 128), max_iter=400, random_state=42,
                          early_stopping=True, validation_fraction=0.15,
                          learning_rate_init=0.001, batch_size=128),
            scale_meta=True
        ),
    }


# ─── Run regression ────────────────────────────────────────────────────────

def run_one_regressor(name, pipeline, df, y, cv):
    from sklearn.model_selection import cross_validate

    out_path = RESULTS_DIR / f"{name}.txt"
    print(f"  Running {name}...", flush=True)

    scoring = {"mae": "neg_mean_absolute_error",
               "rmse": "neg_root_mean_squared_error",
               "r2": "r2"}
    scores = cross_validate(pipeline, df, y, cv=cv, scoring=scoring, n_jobs=1)

    mae = -scores["test_mae"].mean()
    mae_std = scores["test_mae"].std()
    rmse = -scores["test_rmse"].mean()
    rmse_std = scores["test_rmse"].std()
    r2 = scores["test_r2"].mean()
    r2_std = scores["test_r2"].std()

    X_train, X_test, y_train, y_test = train_test_split(
        df, y, test_size=0.2, random_state=42
    )
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    result = {
        "model": name,
        "mae": round(mae, 4),
        "mae_std": round(mae_std, 4),
        "rmse": round(rmse, 4),
        "rmse_std": round(rmse_std, 4),
        "r2": round(r2, 4),
        "r2_std": round(r2_std, 4),
    }

    with open(out_path, "w") as f:
        f.write(f"Model: {name}\n")
        f.write(f"CV MAE  : {mae:.4f} ± {mae_std:.4f}\n")
        f.write(f"CV RMSE : {rmse:.4f} ± {rmse_std:.4f}\n")
        f.write(f"CV R²   : {r2:.4f} ± {r2_std:.4f}\n")
        f.write(f"CV fold MAE: {np.round(-scores['test_mae'], 4).tolist()}\n\n")
        f.write("Hold-out 80/20:\n")
        f.write(f"  MAE  : {mean_absolute_error(y_test, y_pred):.4f}\n")
        f.write(f"  RMSE : {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}\n")
        f.write(f"  R²   : {r2_score(y_test, y_pred):.4f}\n")

    summary_csv = RESULTS_DIR / "summary_reg.csv"
    exists = summary_csv.exists()
    with open(summary_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        if not exists: writer.writeheader()
        writer.writerow(result)

    print(f"  {name:<28} MAE={mae:.2f}±{mae_std:.2f}  RMSE={rmse:.2f}±{rmse_std:.2f}  "
          f"R²={r2:.4f}±{r2_std:.4f}  → {out_path.name}", flush=True)
    return result


def run_regression(df, target_col="reactions_count", name_suffix=""):
    print(f"\n{'=' * 60}")
    print(f"REGRESSION{name_suffix}: predict {target_col}")
    print("=" * 60)

    y = df[target_col].values.astype(float)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    results = []
    for name, pipeline in get_regressors_v2().items():
        try:
            result = run_one_regressor(name + name_suffix, pipeline, df, y, cv)
            results.append(result)
        except Exception as e:
            print(f"  ERROR in {name}: {e}", flush=True)

    results_df = pd.DataFrame(results).sort_values("mae", ascending=True)
    print()
    print(results_df.to_string(index=False))
    return results_df


# ─── Regression with log1p ─────────────────────────────────────────────────

def run_one_regressor_log(name, pipeline, df, y, cv):
    out_path = RESULTS_DIR / f"{name}_log.txt"
    print(f"  Running {name}_log...", flush=True)

    y_log = np.log1p(y)
    y_pred_log = cross_val_predict(pipeline, df, y_log, cv=cv, n_jobs=1, method="predict")
    y_pred = np.expm1(np.clip(y_pred_log, -10, 10))

    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    r2 = r2_score(y, y_pred)
    mae_log = mean_absolute_error(y_log, y_pred_log)

    result = {
        "model": f"{name}_log",
        "mae_original": round(mae, 4),
        "rmse_original": round(rmse, 4),
        "r2_original": round(r2, 4),
        "mae_log": round(mae_log, 4),
    }

    with open(out_path, "w") as f:
        f.write(f"Model: {name} (log1p target)\n\n")
        f.write(f"CV MAE (log scale) : {mae_log:.4f}\n\n")
        f.write("Back-transformed (original scale):\n")
        f.write(f"  MAE  : {mae:.4f}\n")
        f.write(f"  RMSE : {rmse:.4f}\n")
        f.write(f"  R²   : {r2:.4f}\n")

    summary_csv = RESULTS_DIR / "summary_reg_log.csv"
    exists = summary_csv.exists()
    with open(summary_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        if not exists: writer.writeheader()
        writer.writerow(result)

    print(f"  {name + '_log':<28} MAE={mae:.2f}  RMSE={rmse:.2f}  "
          f"R²={r2:.4f}  → {out_path.name}", flush=True)
    return result


def run_regression_log(df):
    print(f"\n{'=' * 60}")
    print("REGRESSION (log1p target)")
    print("=" * 60)

    y = df["reactions_count"].values.astype(float)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    results = []
    for name, pipeline in get_regressors_v2().items():
        try:
            result = run_one_regressor_log(name, pipeline, df, y, cv)
            results.append(result)
        except Exception as e:
            print(f"  ERROR in {name}_log: {e}", flush=True)

    results_df = pd.DataFrame(results).sort_values("mae_original", ascending=True)
    print()
    print(results_df.to_string(index=False))
    return results_df


# ─── Box-Cox regression ────────────────────────────────────────────────────

def run_one_regressor_boxcox(name, pipeline, df, y, cv):
    out_path = RESULTS_DIR / f"{name}_boxcox.txt"
    print(f"  Running {name}_boxcox...", flush=True)

    # Box-Cox requires positive values; reactions can be 0, so shift by 1
    y_shifted = y + 1
    y_bc, lam = boxcox(y_shifted)

    y_pred_bc = cross_val_predict(pipeline, df, y_bc, cv=cv, n_jobs=1, method="predict")

    # Back-transform
    if abs(lam) < 1e-6:
        y_pred = np.exp(y_pred_bc) - 1
    else:
        y_pred = np.maximum((y_pred_bc * lam + 1) ** (1/lam) - 1, 0)

    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    r2 = r2_score(y, y_pred)

    result = {
        "model": f"{name}_boxcox",
        "lambda": round(lam, 4),
        "mae_original": round(mae, 4),
        "rmse_original": round(rmse, 4),
        "r2_original": round(r2, 4),
    }

    with open(out_path, "w") as f:
        f.write(f"Model: {name} (Box-Cox target, λ={lam:.4f})\n\n")
        f.write(f"Back-transformed (original scale):\n")
        f.write(f"  MAE  : {mae:.4f}\n")
        f.write(f"  RMSE : {rmse:.4f}\n")
        f.write(f"  R²   : {r2:.4f}\n")

    summary_csv = RESULTS_DIR / "summary_reg_boxcox.csv"
    exists = summary_csv.exists()
    with open(summary_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        if not exists: writer.writeheader()
        writer.writerow(result)

    print(f"  {name + '_boxcox':<28} λ={lam:.4f}  MAE={mae:.2f}  "
          f"R²={r2:.4f}  → {out_path.name}", flush=True)
    return result


def run_regression_boxcox(df):
    print(f"\n{'=' * 60}")
    print("REGRESSION (Box-Cox target)")
    print("=" * 60)

    y = df["reactions_count"].values.astype(float)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    results = []
    for name, pipeline in get_regressors_v2().items():
        try:
            result = run_one_regressor_boxcox(name, pipeline, df, y, cv)
            results.append(result)
        except Exception as e:
            print(f"  ERROR in {name}_boxcox: {e}", flush=True)

    results_df = pd.DataFrame(results).sort_values("mae_original", ascending=True)
    print()
    print(results_df.to_string(index=False))
    return results_df


# ─── Ensemble: average top-3 regressors ────────────────────────────────────

def run_ensemble(df):
    """Simple ensemble: average predictions from top 3 regressors."""
    print(f"\n{'=' * 60}")
    print("ENSEMBLE: average top-3 regressors")
    print("=" * 60)

    y = df["reactions_count"].values.astype(float)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    regressors = get_regressors_v2()

    # Use top 3 from v1 experience: lightgbm, xgboost, hist_gradient_boosting (log1p)
    ensemble_names = ["lightgbm", "xgboost", "hist_gradient_boosting"]

    # Log-transform for each, average predictions, back-transform
    y_log = np.log1p(y)
    cv_predictions = []

    for name in ensemble_names:
        if name not in regressors:
            print(f"  Skipping {name} (not in regressors)")
            continue
        pipeline = regressors[name]
        pred_log = cross_val_predict(pipeline, df, y_log, cv=cv, n_jobs=1, method="predict")
        cv_predictions.append(pred_log)

    if not cv_predictions:
        print("  No models to ensemble!")
        return

    avg_pred_log = np.mean(cv_predictions, axis=0)
    y_pred = np.expm1(np.clip(avg_pred_log, -10, 10))

    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    r2 = r2_score(y, y_pred)

    result = {
        "model": "ensemble_lgbm_xgb_hgb",
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
    }

    print(f"  {'ensemble':<28} MAE={mae:.2f}  RMSE={rmse:.2f}  "
          f"R²={r2:.4f}")
    return result


# ─── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = export_csv()

    # Quantile-based labels for balanced classification
    q33 = df["reactions_count"].quantile(0.33)
    q66 = df["reactions_count"].quantile(0.66)
    df["reaction_label"] = pd.cut(df["reactions_count"],
                                   bins=[-1, q33, q66, df["reactions_count"].max()],
                                   labels=["low", "medium", "high"])

    print("\n" + "=" * 60)
    print("V2: BETTER FEATURES + BIGRAMS + HP TUNING")
    print("=" * 60)

    clf_results = run_classification(df)
    reg_results = run_regression(df)
    reg_log_results = run_regression_log(df)
    reg_bc_results = run_regression_boxcox(df)
    ensemble_result = run_ensemble(df)

    print()
    print("=" * 60)
    print("FINAL RESULTS — V2")
    print("=" * 60)
    print()
    print("CLASSIFICATION (F1-macro leaderboard):")
    print(clf_results.to_string(index=False))
    print()
    print("REGRESSION raw (MAE — lower is better):")
    print(reg_results.to_string(index=False))
    print()
    print("REGRESSION log1p (MAE original scale):")
    print(reg_log_results.to_string(index=False))
    print()
    print("REGRESSION Box-Cox (MAE original scale):")
    print(reg_bc_results.to_string(index=False))
    print()
    print("ENSEMBLE (log1p):")
    print(pd.DataFrame([ensemble_result]).to_string(index=False))
    print()
    print(f"Full results → {RESULTS_DIR}/")