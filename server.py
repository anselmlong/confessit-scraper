#!/usr/bin/env python3
"""Local web dashboard for NUSConfessIT data.

Usage: python server.py [--port 5000]
"""
import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import re

from flask import Flask, render_template, request, abort, redirect, jsonify
from markupsafe import Markup, escape

from src.storage.db import DB_PATH, init_db

app = Flask(__name__)
app.template_folder = str(Path(__file__).parent / "templates")
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Simple in-memory cache for expensive endpoints
import time as _time
_cache: dict = {}
_CACHE_TTL = 3600  # 1 hour


def _cached(key: str, fn):
    """Return cached result, or compute and cache it."""
    entry = _cache.get(key)
    if entry and _time.monotonic() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    result = fn()
    _cache[key] = {"data": result, "ts": _time.monotonic()}
    return result


_MD_INLINE = re.compile(r'\*\*|__(?=\S)|(?<=\S)__|~~|`|\[([^\]]+)\]\([^\)]+\)')


def _strip_md(text: str) -> str:
    """Strip markdown syntax, keeping link text."""
    return _MD_INLINE.sub(r'\1', text)


def _tg_md_to_html(text: str) -> Markup:
    """Convert Telegram markdown to HTML with paragraph, list, and rule support."""
    s = str(escape(text))
    # inline markup
    s = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)',
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s, flags=re.DOTALL)
    s = re.sub(r'__(.+?)__', r'<em>\1</em>', s, flags=re.DOTALL)
    s = re.sub(r'~~(.+?)~~', r'<del>\1</del>', s, flags=re.DOTALL)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)

    # Line-by-line pass: classify lines into blocks
    blocks: list[tuple[str, object]] = []
    para: list[str] = []
    list_items: list[str] = []

    def flush_para():
        if para:
            blocks.append(('p', list(para)))
            para.clear()

    def flush_list():
        if list_items:
            blocks.append(('ul', list(list_items)))
            list_items.clear()

    for line in s.splitlines():
        stripped = line.strip()
        if stripped == '---':
            flush_para(); flush_list()
            blocks.append(('hr', ''))
        elif re.match(r'^-\s', stripped):
            flush_para()
            list_items.append(stripped[2:].strip())
        elif not stripped:
            flush_para(); flush_list()
        else:
            flush_list()
            para.append(line)
    flush_para(); flush_list()

    # Render blocks
    parts = []
    for btype, bcontent in blocks:
        if btype == 'hr':
            parts.append('<hr>')
        elif btype == 'ul':
            items = ''.join(f'<li>{x}</li>' for x in bcontent)
            parts.append(f'<ul>{items}</ul>')
        else:
            inner = '<br>'.join(bcontent)
            if inner.strip():
                parts.append(f'<p>{inner}</p>')
    return Markup('\n'.join(parts))


app.jinja_env.filters["tgmd"] = _tg_md_to_html

RANGES = {"week": 7, "month": 30, "year": 365, "all": None}
SORTS = {
    "time": "date",
    "score": "(reactions_count + reply_count * 2 + forwards * 3)",
    "reactions": "reactions_count",
    "replies": "reply_count",
}

SCORE_FORMULA = "reactions + replies × 2 + forwards × 3"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _score_expr():
    return "(reactions_count + reply_count * 2 + forwards * 3)"


def _excerpt(text: str, max_chars: int = 300) -> str:
    text = _strip_md((text or "").strip())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def _enrich(rows):
    out = []
    for r in rows:
        p = dict(r)
        p["excerpt"] = _excerpt(p.get("content") or p.get("text") or "")
        p["score"] = p.get("score", 0)
        out.append(p)
    return out


def get_posts(days=None, limit=25, sort="reactions", q=None, order="desc", start_date=None, end_date=None):
    conn = _connect()
    order_expr = SORTS.get(sort, SORTS["reactions"])
    order_dir = "ASC" if order == "asc" else "DESC"
    sql = f"SELECT *, {_score_expr()} AS score FROM messages WHERE is_reply=0"
    params = []
    if days:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        sql += " AND date >= ?"
        params.append(since)
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date + "T23:59:59")
    if q:
        like = f"%{q}%"
        sql += " AND (text LIKE ? OR title LIKE ? OR content LIKE ?)"
        params.extend([like, like, like])
    sql += f" ORDER BY {order_expr} {order_dir} LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return _enrich(rows)


def get_posts_semantic(q, limit=25, days=None, start_date=None, end_date=None):
    """Rank posts by cosine similarity to the query via sqlite-vec.

    Overfetches the KNN so date filters applied afterwards still leave
    enough results. Vectors are scanned on disk — nothing large is held
    in memory per request.
    """
    from src.search.semantic import semantic_search_ids

    k = min(max(limit * 4, 50), 200)
    hits = semantic_search_ids(q, k=k)
    if not hits:
        return []
    rank = {pid: i for i, (pid, _) in enumerate(hits)}
    sims = dict(hits)

    conn = _connect()
    placeholders = ",".join("?" * len(rank))
    sql = (f"SELECT *, {_score_expr()} AS score FROM messages "
           f"WHERE is_reply=0 AND id IN ({placeholders})")
    params = list(rank)
    if days:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        sql += " AND date >= ?"
        params.append(since)
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date + "T23:59:59")
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    posts = _enrich(rows)
    posts.sort(key=lambda p: rank.get(p["id"], len(rank)))
    for p in posts:
        p["similarity"] = round(sims.get(p["id"], 0.0), 3)
    return posts[:limit]


def get_overview_stats():
    conn = _connect()
    r = conn.execute("""
        SELECT
            COUNT(*) as total,
            MIN(date) as first_date,
            MAX(date) as last_date,
            SUM(views) as total_views,
            ROUND(AVG(reactions_count), 1) as avg_reactions,
            ROUND(AVG(word_count), 0) as avg_words,
            MAX(reactions_count) as max_reactions
        FROM messages WHERE is_reply=0
    """).fetchone()
    total_replies = conn.execute("SELECT COUNT(*) FROM replies").fetchone()[0]
    conn.close()
    d = dict(r)
    d["total_replies"] = total_replies
    d["first_date"] = (d["first_date"] or "")[:10]
    d["last_date"] = (d["last_date"] or "")[:10]
    d["total_views"] = int(d["total_views"] or 0)
    d["avg_reactions"] = round(d["avg_reactions"] or 0, 1)
    d["avg_words"] = int(d["avg_words"] or 0)
    d["max_reactions"] = int(d["max_reactions"] or 0)
    try:
        d1 = datetime.fromisoformat(d["first_date"])
        d2 = datetime.fromisoformat(d["last_date"])
        d["days_active"] = (d2 - d1).days
    except Exception:
        d["days_active"] = 0
    return d


def get_monthly_counts():
    conn = _connect()
    rows = conn.execute("""
        SELECT strftime('%Y-%m', date) as month, COUNT(*) as cnt
        FROM messages WHERE is_reply=0 AND date IS NOT NULL
        GROUP BY month ORDER BY month DESC LIMIT 18
    """).fetchall()
    conn.close()
    data = [(r["month"], r["cnt"]) for r in rows]
    data.reverse()
    return data



def get_total_posts():
    conn = _connect()
    n = conn.execute("SELECT COUNT(*) FROM messages WHERE is_reply=0").fetchone()[0]
    conn.close()
    return n


def get_post_and_replies(post_id: int):
    conn = _connect()
    post = conn.execute(
        f"SELECT *, {_score_expr()} AS score FROM messages WHERE id=? AND is_reply=0",
        (post_id,)
    ).fetchone()
    if not post:
        conn.close()
        return None, [], 0
    # Inline replies from the channel itself
    inline = conn.execute(
        "SELECT * FROM messages WHERE reply_to_msg_id=? ORDER BY date ASC",
        (post_id,)
    ).fetchall()
    # Replies from linked discussion group
    discussion = conn.execute(
        "SELECT * FROM replies WHERE post_id=? ORDER BY date ASC",
        (post_id,)
    ).fetchall()
    total_in_group = conn.execute(
        "SELECT COUNT(*) FROM replies WHERE post_id=?", (post_id,)
    ).fetchone()[0]
    conn.close()
    return dict(post), [dict(r) for r in inline] + [dict(r) for r in discussion], total_in_group


@app.route("/")
def index():
    range_key = request.args.get("range", "week")
    if range_key not in RANGES:
        range_key = "week"
    n = min(int(request.args.get("n", 25)), 200)
    sort_key = request.args.get("sort", "reactions")
    if sort_key not in SORTS:
        sort_key = "reactions"
    q = request.args.get("q", "").strip()
    days = RANGES[range_key]

    conn = _connect()
    count_q = "SELECT COUNT(*) FROM messages WHERE is_reply=0"
    params = []
    if days:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        count_q += " AND date >= ?"
        params.append(since)
    total = conn.execute(count_q, params).fetchone()[0]
    conn.close()

    posts = get_posts(days=days, limit=n, sort=sort_key, q=q or None)
    stats = get_overview_stats()
    monthly = get_monthly_counts()
    max_monthly = max(c for _, c in monthly) if monthly else 1

    return render_template("index.html",
        active_page="home",
        posts=posts,
        stats=stats,
        monthly=monthly,
        max_monthly=max_monthly,
        range_key=range_key,
        sort_key=sort_key,
        q=q,
        n=n,
        total=total,
    )


@app.route("/top")
def top():
    qs = request.query_string.decode()
    return redirect(f"/?{qs}" if qs else "/")


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    return redirect(f"/?q={q}&sort=reactions" if q else "/")


@app.route("/post/<int:post_id>")
def post(post_id):
    p, replies, total_in_group = get_post_and_replies(post_id)
    if not p:
        abort(404)
    tg_url = f"https://t.me/NUSConfessIT/{post_id}"
    return render_template("post.html", active_page="", post=p, replies=replies,
                           total_in_group=total_in_group, tg_url=tg_url)


# ── JSON API endpoints ────────────────────────────────────────────

@app.after_request
def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@app.route("/api/stats")
def api_stats():
    """Overall stats + landscape findings."""
    conn = _connect()
    raw = conn.execute("""
        SELECT
            COUNT(*) AS total,
            MIN(date) AS first_date,
            MAX(date) AS last_date,
            SUM(views) AS total_views,
            ROUND(AVG(reactions_count), 1) AS avg_reactions,
            ROUND(AVG(word_count), 0) AS avg_words,
            MAX(reactions_count) AS max_reactions
        FROM messages WHERE is_reply=0
    """).fetchone()
    total_replies = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE is_reply=1"
    ).fetchone()[0]
    conn.close()

    first_date = (raw[1] or "")[:10]
    last_date = (raw[2] or "")[:10]
    try:
        days_active = (datetime.fromisoformat(last_date) - datetime.fromisoformat(first_date)).days
    except:
        days_active = 0

    return jsonify({
        "total_posts": raw[0],
        "total_replies": total_replies,
        "first_date": first_date,
        "last_date": last_date,
        "days_active": days_active,
        "total_views": raw[3] or 0,
        "avg_reactions": raw[4] or 0,
        "avg_words": raw[5] or 0,
        "max_reactions": raw[6] or 0,
        "score_formula": SCORE_FORMULA,
    })


@app.route("/api/monthly")
def api_monthly():
    conn = _connect()
    rows = conn.execute("""
        SELECT strftime('%Y-%m', date) AS month, COUNT(*) AS cnt
        FROM messages WHERE is_reply=0 AND date IS NOT NULL
        GROUP BY month ORDER BY month DESC LIMIT 18
    """).fetchall()
    conn.close()
    return jsonify([{"month": r[0], "count": r[1]} for r in rows][::-1])


@app.route("/api/posts")
def api_posts():
    range_key = request.args.get("range", "month")
    sort_key = request.args.get("sort", "reactions")
    order_key = request.args.get("order", "desc")
    limit = min(int(request.args.get("n", 25)), 200)
    q = request.args.get("q", "").strip()
    mode = request.args.get("mode", "keyword")
    start_date = request.args.get("start_date", "").strip() or None
    end_date = request.args.get("end_date", "").strip() or None

    rows = None
    if mode == "semantic" and q:
        try:
            rows = get_posts_semantic(
                q,
                limit=limit,
                days=RANGES.get(range_key) if not start_date else None,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            app.logger.warning("semantic search failed, falling back: %s", e)
    if rows is None:
        rows = get_posts(
            days=RANGES.get(range_key) if not start_date else None,
            limit=limit,
            sort=sort_key if sort_key in SORTS else "reactions",
            order=order_key if order_key in ("asc", "desc") else "desc",
            q=q or None,
            start_date=start_date,
            end_date=end_date,
        )
    return jsonify([{
        "id": p["id"],
        "title": p.get("title") or "",
        "excerpt": p["excerpt"],
        "date": p.get("date", ""),
        "reactions": p.get("reactions_count", 0),
        "replies": p.get("reply_count", 0),
        "forwards": p.get("forwards", 0),
        "score": p["score"],
        "category": p.get("category", ""),
        "views": p.get("views", 0),
        **({"similarity": p["similarity"]} if "similarity" in p else {}),
    } for p in rows])


@app.route("/api/post/<int:post_id>")
def api_post(post_id):
    p, replies, total = get_post_and_replies(post_id)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "post": {
            "id": p["id"],
            "title": p.get("title") or "",
            "body": p.get("content") or p.get("text") or "",
            "date": (p.get("date") or ""),
            "reactions": p.get("reactions_count", 0),
            "replies": p.get("reply_count", 0),
            "forwards": p.get("forwards", 0),
            "score": p.get("score", 0),
            "category": p.get("category", ""),
            "views": p.get("views", 0),
        },
        "replies": [{
            "id": r["id"],
            "body": r.get("content") or r.get("text") or "",
            "date": (r.get("date") or "")[:10],
        } for r in replies],
        "total_replies_in_group": total,
    })


def _compute_landscape():
    from collections import Counter
    import numpy as np

    conn = _connect()
    rows = conn.execute(
        "SELECT id, text, reactions_count, reply_count, forwards, category "
        "FROM messages WHERE is_reply=0"
    ).fetchall()
    conn.close()

    CAT_RE = re.compile(r'^\*{2}#(\w+)\*{2}')

    def extract_cat(text):
        m = CAT_RE.match(text or "")
        return m.group(1).lower() if m else "unknown"

    scores = [r[2] * 1 + r[3] * 2 + r[4] * 3 for r in rows]
    arr = np.array(scores)
    th = float(np.percentile(arr, 75))
    cat_counts = Counter(extract_cat(r[1]) for r in rows)
    top_posts = sorted(
        [(r[0], r[2] * 1 + r[3] * 2 + r[4] * 3, r[1] or "") for r in rows],
        key=lambda x: -x[1],
    )[:10]

    return {
        "total_posts": len(rows),
        "viral_threshold": round(th, 1),
        "viral_rate": round(float((arr >= th).mean()), 3),
        "categories": dict(cat_counts.most_common()),
        "score_distribution": {
            "mean": round(float(arr.mean()), 1),
            "median": round(float(np.median(arr)), 1),
            "p75": round(float(th), 1),
            "p90": round(float(np.percentile(arr, 90)), 1),
            "max": int(arr.max()),
        },
        "top_posts": [
            {"id": p[0], "score": p[1], "excerpt": _excerpt(p[2], 150)}
            for p in top_posts
        ],
        "cluster_taxonomy": {
            "4_main_regions": {
                "academics": {"size_pct": 32, "keywords": "mods, finals, major, course, lecture"},
                "career_and_hot_takes": {"size_pct": 31, "keywords": "internship, work, students, linkedin, hustle"},
                "dating_and_relationships": {"size_pct": 29, "keywords": "girl, guys, love, crush, friend"},
                "lonely_and_admin": {"size_pct": 8, "keywords": "bored, chat, sleep, wanna, swap"},
            },
            "method": "UMAP (15k fit, 65k transform) + Mean Shift (bandwidth=2.14) + HDBSCAN validation",
            "embedding_model": "openai/text-embedding-3-small (512d)",
        },
    }


@app.route("/api/landscape")
def api_landscape():
    """Embedding landscape findings from ML analysis."""
    return jsonify(_cached("landscape", _compute_landscape))


# ── ML Insights ─────────────────────────────────────────────────────────────

_HOOK_KWS = ["am i the only one", "hot take", "unpopular opinion", "am i wrong",
             "does anyone else", "tell me i'm not", "is it just me", "cmv"]
_CTA_KWS = ["react", "vote", "what do you think", "comment", "thoughts?", "opinions?",
            "what would you", "what should i", "agree", "disagree"]
_CURSE_KWS = ["fuck", "shit", "damn", "bitch", "ass", "wtf", "stfu", "hell",
              "suck", "crap", "piss", "dick"]
_REL_KWS = ["bf", "gf", "boyfriend", "girlfriend", "crush", "cheat", "cheating",
            "ex", "relationship", "dating", "date", "love", "breakup", "broke up",
            "husband", "wife", "partner"]
_ACAD_KWS = ["exam", "exams", "gpa", "cap", "fail", "failed", "grade", "deadline",
             "project", "assignment", "study", "studying", "lecture", "tutorial", "quiz",
             "midterm", "final", "semester", "mods", "module", "homework", "stress"]


def _compute_insights():
    import json
    import numpy as np
    from collections import defaultdict

    conn = _connect()
    rows = conn.execute(
        "SELECT id, date, COALESCE(NULLIF(content,''),NULLIF(text,'')) AS body, "
        "reactions_count, reply_count, forwards, category, word_count "
        "FROM messages WHERE is_reply=0 AND word_count > 0"
    ).fetchall()
    conn.close()

    if not rows:
        return {"error": "no data"}

    records = []
    for r in rows:
        pid, date_str, body, rc, rpc, fw, cat, wc = r
        body = body or ""
        score = (rc or 0) * 1 + (rpc or 0) * 2 + (fw or 0) * 3
        txt_lower = body.lower()

        emoji_count = sum(1 for c in body if ord(c) > 0x1F300)
        has_question = int("?" in body)
        cat_clean = (cat or "unknown").split()[0].lower() if cat else "unknown"
        hook_count = sum(txt_lower.count(k) for k in _HOOK_KWS)
        cta_count = sum(txt_lower.count(k) for k in _CTA_KWS)
        curse_count = sum(txt_lower.count(k) for k in _CURSE_KWS)
        rel_density = sum(txt_lower.count(k) for k in _REL_KWS) / max(wc, 1)
        acad_density = sum(txt_lower.count(k) for k in _ACAD_KWS) / max(wc, 1)
        ellipsis = body.count("...") + body.count("…")
        allcaps = sum(1 for w in body.split() if len(w) > 2 and w.isupper())
        line_count = body.count("\n") + 1

        h = d = -1
        try:
            dt = datetime.fromisoformat(date_str)
            h = dt.hour
            d = dt.weekday()
        except Exception:
            pass
        if h < 6: hour_bin = 0
        elif h < 12: hour_bin = 1
        elif h < 14: hour_bin = 2
        elif h < 18: hour_bin = 3
        elif h < 22: hour_bin = 4
        else: hour_bin = 5

        if wc < 20: len_bin = "short"
        elif wc < 80: len_bin = "medium"
        else: len_bin = "long"

        records.append({
            "score": score, "cat": cat_clean,
            "wc": wc, "line_count": line_count,
            "hour": h, "dow": d, "hour_bin": hour_bin, "len_bin": len_bin,
            "emc": emoji_count, "hq": has_question,
            "hook": hook_count, "cta": cta_count,
            "curse": curse_count, "ellipsis": ellipsis,
            "allcaps": allcaps, "rel_density": rel_density,
            "acad_density": acad_density,
        })

    all_scores = np.array([r["score"] for r in records])

    # ── 1. Category virality ──
    cat_buckets = defaultdict(list)
    for r in records:
        cat_buckets[r["cat"]].append(r["score"])
    cat_stats = []
    for cat, scs in cat_buckets.items():
        if len(scs) < 10:
            continue
        arr_cat = np.array(scs)
        cat_stats.append({
            "category": cat.capitalize(),
            "post_count": len(scs),
            "avg_score": round(float(arr_cat.mean()), 1),
            "median_score": round(float(np.median(arr_cat)), 1),
            "viral_rate": round(float((arr_cat >= np.percentile(all_scores, 75)).mean()), 3),
        })
    cat_stats.sort(key=lambda x: -x["viral_rate"])

    # ── 2. Hour bins ──
    HOUR_LABELS = ["Night (12-6am)", "Morning (6-12pm)", "Lunch (12-2pm)",
                   "Afternoon (2-6pm)", "Evening (6-10pm)", "Late (10pm-12am)"]
    hour_buckets = defaultdict(list)
    for r in records:
        if r["hour"] >= 0:
            hour_buckets[r["hour_bin"]].append(r["score"])
    hour_impact = [
        {"label": HOUR_LABELS[b], "avg_score": round(float(np.array(s).mean()), 1), "post_count": len(s)}
        for b, s in sorted(hour_buckets.items())
    ]

    # ── 3. Day of week ──
    DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_buckets = defaultdict(list)
    for r in records:
        if r["dow"] >= 0:
            dow_buckets[r["dow"]].append(r["score"])
    dow_impact = [
        {"day": DAY_NAMES[d], "avg_score": round(float(np.array(s).mean()), 1), "post_count": len(s)}
        for d, s in sorted(dow_buckets.items())
    ]

    # ── 4. Length bins ──
    len_buckets = defaultdict(list)
    for r in records:
        len_buckets[r["len_bin"]].append(r["score"])
    len_impact = [
        {"label": label, "avg_score": round(float(np.array(len_buckets[label]).mean()), 1),
         "post_count": len(len_buckets[label])}
        for label in ["short", "medium", "long"]
    ]

    # ── 5. Feature correlations ──
    feature_cols = [
        ("emc", "Emoji count", "number"),
        ("hq", "Has question", "bool"),
        ("line_count", "Line count", "number"),
        ("rel_density", "Relationship density", "number"),
        ("acad_density", "Academic density", "number"),
        ("allcaps", "All-caps words", "number"),
        ("ellipsis", "Ellipsis count", "number"),
        ("curse", "Curse words", "number"),
        ("hook", "Rhetorical hooks", "number"),
        ("cta", "Calls to action", "number"),
    ]
    features = []
    for key, label, ftype in feature_cols:
        vals = np.array([r[key] for r in records], dtype=float)
        corr = float(np.corrcoef(vals, all_scores)[0, 1])
        if ftype == "bool":
            present = all_scores[vals > 0]
            absent = all_scores[vals == 0]
            boost = float(present.mean() - absent.mean()) if len(present) and len(absent) else 0.0
            features.append({"feature": label, "correlation": round(corr, 3),
                              "boost": round(boost, 1),
                              "has_pct": round(float((vals > 0).mean() * 100), 1)})
        else:
            med = float(np.median(vals))
            high = all_scores[vals > med]
            low = all_scores[vals <= med]
            boost = float(high.mean() - low.mean()) if len(high) and len(low) else 0.0
            features.append({"feature": label, "correlation": round(corr, 3),
                              "boost": round(boost, 1)})
    features.sort(key=lambda x: -abs(x["correlation"]))

    # ── 6. ML pipeline feature importance ──
    ml_importance = None
    try:
        ml_path = Path(__file__).parent / "data" / "ml_results" / "feature_importance.json"
        if ml_path.exists():
            ml_importance = json.loads(ml_path.read_text())
    except Exception:
        pass

    return {
        "category_virality": cat_stats,
        "hour_impact": hour_impact,
        "day_impact": dow_impact,
        "length_impact": len_impact,
        "feature_correlations": features,
        "ml_importance": ml_importance,
        "baseline_avg_score": round(float(all_scores.mean()), 1),
    }


@app.route("/api/insights")
def api_insights():
    """Feature insights: what predicts higher scores."""
    result = _cached("insights", _compute_insights)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


# ── Copypasta Detection ─────────────────────────────────────────────────────

_COPYPASTA_TEMPLATES = {
    "st2334_copypasta": {
        "triggers": ["never understand why ppl just dowan to take st2334",
                     "never understand why people would still debate and compare between math and cs"],
        "name": "ST2334/Math vs CS",
    },
    "time_reminder": {
        "triggers": ["time now is"],
        "name": "Time Reminder",
    },
    "graduated_danang": {
        "triggers": ["year 4 student that just graduated", "da nang solo"],
        "name": "Da Nang Trip",
    },
    "mcd_story": {
        "triggers": ["i'm a guy and i work as a service crew in mcd"],
        "name": "McD Crew Story",
    },
    "slay_guy": {
        "triggers": ["slay guy here, looking for find another slay guy"],
        "name": "Slay Guy",
    },
    "bored_m_chat": {
        "triggers": ["bored m here looking to chat with another m about"],
        "name": "Bored M Chat",
    },
    "single_touched_starved": {
        "triggers": ["been single for way too long i m so touched starved"],
        "name": "Single Touched Starved",
    },
    "homeless_osa": {
        "triggers": ["am homeless, osa doesn't give two shits"],
        "name": "Homeless / OSA",
    },
    "bza_vs_dsa": {
        "triggers": ["let's settle this", "bza is simply a stronger choice"],
        "name": "BZA vs DSA",
    },
    "asean_scholarship": {
        "triggers": ["asean scholarship fair", "malaysia and indoen"],
        "name": "ASEAN Scholarship",
    },
    "hall_sublet": {
        "triggers": ["looking for hall sublet next semester"],
        "name": "Hall Sublet",
    },
    "netflix_chill": {
        "triggers": ["netfkix and chill", "binge ginny & georgia"],
        "name": "Netflix & Chill",
    },
    "dear_students_osa": {
        "triggers": ["dear students", "school would like to remind you"],
        "name": "Fake OSA Letter",
    },
    "finding_room": {
        "triggers": ["finding a room (m) for house, pgpr, utr"],
        "name": "Finding Room",
    },
    "keep_items_campus": {
        "triggers": ["keep ur items safely on campus in summer break"],
        "name": "Summer Storage",
    },
    "case_competition": {
        "triggers": ["aag-nus case competition"],
        "name": "Case Competition",
    },
    "crochet_club": {
        "triggers": ["starting a crochet club"],
        "name": "Crochet Club",
    },
}


def _compute_copypasta():
    from datetime import datetime, timedelta, timezone

    conn = _connect()
    rows = conn.execute(
        "SELECT id, text, content, date, reactions_count, reply_count, forwards "
        "FROM messages WHERE is_reply=0"
    ).fetchall()
    conn.close()

    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    clusters = []
    for key, template in _COPYPASTA_TEMPLATES.items():
        matches = []
        for r in rows:
            pid, txt, content, date_str, rc, rpc, fw = r
            body = (content or txt or "").lower()
            # Normalize apostrophes and other unicode punctuation for matching
            body = body.replace("\u2019", "'").replace("\u2018", "'")
            if not all(t in body for t in template["triggers"]):
                continue
            score = (rc or 0) * 1 + (rpc or 0) * 2 + (fw or 0) * 3
            matches.append((pid, (content or txt or ""), score, rc or 0, date_str or ""))

        if not matches:
            continue

        scores = [m[2] for m in matches]
        recent = sum(1 for m in matches if m[4] >= thirty_days_ago)
        sample = matches[0][1][:200]

        clusters.append({
            "key": key,
            "name": template["name"],
            "count": len(matches),
            "avg_score": round(sum(scores) / len(scores), 1),
            "avg_reactions": round(sum(m[3] for m in matches) / len(matches), 1),
            "sample_text": sample,
            "sample_id": matches[0][0],
            "trend_30d": recent,
            "is_trending": recent >= 3,
        })

    clusters.sort(key=lambda c: -c["count"])

    # Exact duplicate stats
    from collections import Counter
    text_counts = Counter()
    for r in rows:
        body = (r[2] or r[1] or "").strip()
        if body:
            text_counts[body] += 1
    exact_dupes = {k: v for k, v in text_counts.items() if v >= 2}
    dupe_pct = round(len(exact_dupes) / len(text_counts) * 100, 1) if text_counts else 0
    total_dupe_posts = sum(v for v in exact_dupes.values()) - len(exact_dupes)

    return {
        "clusters": clusters,
        "exact_duplicates": {
            "unique_texts": len(exact_dupes),
            "total_duplicate_posts": total_dupe_posts,
            "pct_of_all_posts": dupe_pct,
        },
    }


@app.route("/api/copypasta")
def api_copypasta():
    return jsonify(_cached("copypasta", _compute_copypasta))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    init_db()
    print(f"Dashboard running at http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
