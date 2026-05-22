#!/usr/bin/env python3
"""Top confessions leaderboard — Reddit-style ranking by engagement score.

Score = reactions × 3 + replies × 2 + forwards

Usage:
  python top.py                        # top 25 all-time, HTML + table
  python top.py --range week           # past 7 days
  python top.py --range month --top 50 # top 50 this month
  python top.py --no-html              # CLI table only
"""
import argparse
import os
import sqlite3
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table
from rich import box

from src.storage.db import DB_PATH, init_db

RANGES = {
    "week":  7,
    "month": 30,
    "year":  365,
    "all":   None,
}

RANGE_LABELS = {
    "week":  "Past 7 days",
    "month": "Past 30 days",
    "year":  "Past year",
    "all":   "All time",
}

console = Console()


def _score_expr():
    return "(reactions_count * 3 + reply_count * 2 + forwards)"


def get_top(limit: int, days: int | None) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = f"""
        SELECT *, {_score_expr()} AS score
        FROM messages
        WHERE is_reply = 0
    """
    params: list = []
    if days:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query += " AND date >= ?"
        params.append(since)
    query += f" ORDER BY score DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_range_stats(days: int | None) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = f"""
        SELECT
            COUNT(*) AS total,
            MAX({_score_expr()}) AS max_score,
            AVG(reactions_count) AS avg_reactions,
            SUM(views) AS total_views
        FROM messages
        WHERE is_reply = 0
    """
    params: list = []
    if days:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query += " AND date >= ?"
        params.append(since)
    row = dict(conn.execute(query, params).fetchone())
    conn.close()
    return row


def print_table(posts: list[dict], range_label: str):
    table = Table(
        title=f"Top Confessions — {range_label}",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold #003D7C on white",
    )
    table.add_column("#", style="bold", width=3, justify="right")
    table.add_column("Score", style="bold yellow", width=7, justify="right")
    table.add_column("❤️", width=5, justify="right")
    table.add_column("💬", width=5, justify="right")
    table.add_column("↗", width=5, justify="right")
    table.add_column("Date", width=10)
    table.add_column("Confession", no_wrap=False, min_width=40)

    for i, p in enumerate(posts, 1):
        title = p.get("title") or ""
        content = p.get("content") or p.get("text") or ""
        preview = (title + (" — " if title else "") + content)[:120].replace("\n", " ")
        if len(title + content) > 120:
            preview += "…"
        table.add_row(
            str(i),
            str(p.get("score", 0)),
            str(p.get("reactions_count", 0)),
            str(p.get("reply_count", 0)),
            str(p.get("forwards", 0)),
            (p.get("date") or "")[:10],
            preview,
        )

    console.print(table)


def _excerpt(post: dict, max_chars: int = 350) -> str:
    text = post.get("content") or post.get("text") or ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def render_html(posts: list[dict], range_key: str, stats: dict, limit: int) -> str:
    reports_dir = Path(__file__).parent / "reports"
    env = Environment(loader=FileSystemLoader(str(reports_dir)), autoescape=False)
    template = env.get_template("top_template.html")

    enriched = []
    for i, p in enumerate(posts, 1):
        enriched.append({
            **p,
            "rank": i,
            "score": p.get("score", 0),
            "excerpt": _excerpt(p),
            "date_short": (p.get("date") or "")[:10],
        })

    return template.render(
        posts=enriched,
        range_key=range_key,
        range_label=RANGE_LABELS[range_key],
        stats=stats,
        limit=limit,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Top confessions leaderboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python top.py                        # top 25 all-time
  python top.py --range week           # past 7 days
  python top.py --range month --top 50
  python top.py --no-html              # table only, no file written
        """,
    )
    parser.add_argument("--range", choices=list(RANGES), default="all",
                        help="Time range (default: all)")
    parser.add_argument("--top", type=int, default=25, metavar="N",
                        help="Number of posts to show (default: 25)")
    parser.add_argument("--no-html", action="store_true",
                        help="Skip HTML generation, print table only")
    parser.add_argument("--open", action="store_true",
                        help="Open HTML report in browser after generating")
    args = parser.parse_args()

    init_db()

    days = RANGES[args.range]
    range_label = RANGE_LABELS[args.range]

    posts = get_top(limit=args.top, days=days)
    stats = get_range_stats(days=days)

    if not posts:
        console.print(f"[yellow]No confessions found for range: {range_label}[/yellow]")
        return

    print_table(posts, range_label)

    if not args.no_html:
        html = render_html(posts, args.range, stats, args.top)
        out_path = Path(__file__).parent / "reports" / f"top_{args.range}.html"
        out_path.write_text(html, encoding="utf-8")
        console.print(f"\n[green]HTML saved →[/green] {out_path}")
        if args.open:
            webbrowser.open(str(out_path))


if __name__ == "__main__":
    main()
