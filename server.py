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
    "score": "(reactions_count * 3 + reply_count * 2 + forwards)",
    "reactions": "reactions_count",
    "replies": "reply_count",
}

SCORE_FORMULA = "reactions × 3 + replies × 2 + forwards"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _score_expr():
    return "(reactions_count * 3 + reply_count * 2 + forwards)"


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
    start_date = request.args.get("start_date", "").strip() or None
    end_date = request.args.get("end_date", "").strip() or None

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
        "date": p.get("date", "")[:10],
        "reactions": p.get("reactions_count", 0),
        "replies": p.get("reply_count", 0),
        "forwards": p.get("forwards", 0),
        "score": p["score"],
        "category": p.get("category", ""),
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
            "date": (p.get("date") or "")[:10],
            "reactions": p.get("reactions_count", 0),
            "replies": p.get("reply_count", 0),
            "forwards": p.get("forwards", 0),
            "score": p.get("score", 0),
            "category": p.get("category", ""),
        },
        "replies": [{
            "id": r["id"],
            "body": r.get("content") or r.get("text") or "",
            "date": (r.get("date") or "")[:10],
        } for r in replies],
        "total_replies_in_group": total,
    })


@app.route("/api/landscape")
def api_landscape():
    """Embedding landscape findings from ML analysis."""
    from collections import Counter
    import numpy as np
    import re

    conn = _connect()
    rows = conn.execute(
        "SELECT id, text, reactions_count, reply_count, forwards, category "
        "FROM messages WHERE is_reply=0"
    ).fetchall()
    conn.close()

    CAT_RE = re.compile(r'^\*{2}#(\w+)\*{2}')
    def extract_cat(text):
        m = CAT_RE.match(text or "")
        if m:
            return m.group(1).lower()
        return "unknown"

    scores = [r[2]*1 + r[3]*2 + r[4]*3 for r in rows]
    arr = np.array(scores)
    th = float(np.percentile(arr, 75))

    # Categories extracted from text (91% coverage) vs DB field (21% coverage)
    cat_counts = Counter(extract_cat(r[1]) for r in rows)

    # Viral hotspots
    top_posts = sorted(
        [(r[0], r[2]*1 + r[3]*2 + r[4]*3, r[1] or "") for r in rows],
        key=lambda x: -x[1]
    )[:10]

    return jsonify({
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
        "top_posts": [{
            "id": p[0], "score": p[1],
            "excerpt": _excerpt(p[2], 150),
        } for p in top_posts],
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
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    init_db()
    print(f"Dashboard running at http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
