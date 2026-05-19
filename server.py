#!/usr/bin/env python3
"""Local web dashboard for NUSConfessIT data.

Usage: python server.py [--port 5000]
"""
import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import re

from flask import Flask, render_template, request, abort
from markupsafe import Markup, escape

from src.storage.db import DB_PATH, init_db

app = Flask(__name__)
app.template_folder = str(Path(__file__).parent / "templates")


def _tg_md_to_html(text: str) -> Markup:
    """Convert Telegram markdown to safe HTML."""
    s = str(escape(text))  # escape HTML first
    # links: [text](url)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)',
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    # bold: **text**
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s, flags=re.DOTALL)
    # italic: __text__
    s = re.sub(r'__(.+?)__', r'<em>\1</em>', s, flags=re.DOTALL)
    # strikethrough: ~~text~~
    s = re.sub(r'~~(.+?)~~', r'<del>\1</del>', s, flags=re.DOTALL)
    # inline code: `text`
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return Markup(s)


app.jinja_env.filters["tgmd"] = _tg_md_to_html

RANGES = {"week": 7, "month": 30, "year": 365, "all": None}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _score_expr():
    return "(reactions_count * 3 + reply_count * 2 + forwards)"


def _excerpt(text: str, max_chars: int = 300) -> str:
    text = (text or "").strip()
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


def get_top(days=None, limit=25):
    conn = _connect()
    q = f"SELECT *, {_score_expr()} AS score FROM messages WHERE is_reply=0"
    params = []
    if days:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q += " AND date >= ?"
        params.append(since)
    q += " ORDER BY score DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
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


def search_posts(query: str, limit=50):
    conn = _connect()
    like = f"%{query}%"
    rows = conn.execute(f"""
        SELECT *, {_score_expr()} AS score
        FROM messages
        WHERE is_reply=0 AND (text LIKE ? OR title LIKE ? OR content LIKE ?)
        ORDER BY score DESC LIMIT ?
    """, (like, like, like, limit)).fetchall()
    conn.close()
    return _enrich(rows)


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
    stats = get_overview_stats()
    monthly = get_monthly_counts()
    max_monthly = max(c for _, c in monthly) if monthly else 1
    top_week = get_top(days=7, limit=5)
    return render_template("index.html",
        active_page="home",
        stats=stats,
        monthly=monthly,
        max_monthly=max_monthly,
        top_week=top_week,
    )


@app.route("/top")
def top():
    range_key = request.args.get("range", "all")
    if range_key not in RANGES:
        range_key = "all"
    n = min(int(request.args.get("n", 25)), 200)
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

    posts = get_top(days=days, limit=n)
    return render_template("top.html",
        active_page="top",
        posts=posts,
        range_key=range_key,
        n=n,
        total=total,
    )


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = search_posts(q) if q else []
    return render_template("search.html",
        active_page="search",
        q=q,
        results=results,
        total_posts=get_total_posts(),
    )


@app.route("/post/<int:post_id>")
def post(post_id):
    p, replies, total_in_group = get_post_and_replies(post_id)
    if not p:
        abort(404)
    tg_url = f"https://t.me/NUSConfessIT/{post_id}"
    return render_template("post.html", active_page="", post=p, replies=replies,
                           total_in_group=total_in_group, tg_url=tg_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    init_db()
    print(f"Dashboard running at http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
