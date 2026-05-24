#!/usr/bin/env python3
"""Refresh reaction counts, views, and forwards for top and recent posts.

Fetches fresh engagement data directly from Telegram for:
  - The top N posts by score  (default: 500)
  - All posts from the last N days  (default: 30)

This keeps the dashboard counts accurate without a full re-scrape.
Run it on a separate cron schedule — e.g. every hour or every few hours.

Usage:
  python refresh_reactions.py                   # top 500 + last 30 days
  python refresh_reactions.py --top 1000        # wider top-post coverage
  python refresh_reactions.py --days 7          # last week only
  python refresh_reactions.py --channel https://t.me/...
"""
import argparse
import sys
import time

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

from src.logger import setup_logging
from src.scraper import refresh_reactions
from src.storage.db import init_db, get_top_post_ids, get_recent_post_ids, update_reactions_bulk

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Refresh reaction counts for top and recent posts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python refresh_reactions.py               # top 500 posts + last 30 days
  python refresh_reactions.py --top 1000   # expand top-post coverage
  python refresh_reactions.py --days 7     # last week only
        """,
    )
    parser.add_argument("--channel", default="https://t.me/NUSConfessIT",
                        help="Telegram channel URL (default: NUSConfessIT)")
    parser.add_argument("--top", type=int, default=500,
                        help="Top N posts by score to refresh (default: 500)")
    parser.add_argument("--days", type=int, default=30,
                        help="Also refresh posts from the last N days (default: 30)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    setup_logging(args.log_level)

    console.print(Panel.fit(
        "[bold blue]Reaction Refresh[/bold blue]\n"
        f"[dim]Top {args.top} posts · last {args.days} days[/dim]",
        border_style="blue",
    ))

    try:
        init_db()
    except RuntimeError as e:
        console.print(f"[bold red]Database error:[/bold red] {e}")
        sys.exit(1)

    top_ids = set(get_top_post_ids(limit=args.top))
    recent_ids = set(get_recent_post_ids(days=args.days))
    post_ids = sorted(top_ids | recent_ids, reverse=True)  # newest-first for nicer progress

    overlap = len(top_ids & recent_ids)
    console.print(
        f"[dim]{len(post_ids)} posts targeted "
        f"({len(top_ids)} top, {len(recent_ids)} recent, {overlap} overlap)[/dim]"
    )

    if not post_ids:
        console.print("[yellow]No posts found in database — nothing to refresh.[/yellow]")
        return

    start = time.monotonic()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[bold blue]{task.fields[count]}[/bold blue] / "
                   f"{len(post_ids)} fetched"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching from Telegram...", total=len(post_ids), count=0)

        try:
            updates = refresh_reactions(
                args.channel,
                post_ids=post_ids,
                progress_callback=lambda n: progress.update(task, count=n, completed=n),
            )
        except ValueError as e:
            console.print(f"\n[bold red]Configuration error:[/bold red] {e}")
            sys.exit(1)
        except RuntimeError as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            sys.exit(2)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            sys.exit(0)

    try:
        updated = update_reactions_bulk(updates)
    except RuntimeError as e:
        console.print(f"[bold red]DB write failed:[/bold red] {e}")
        sys.exit(1)

    elapsed = time.monotonic() - start

    console.print(Panel(
        f"[bold green]Done![/bold green]\n\n"
        f"  Posts targeted:  [bold]{len(post_ids)}[/bold]\n"
        f"  Fetched:         [bold]{len(updates)}[/bold]\n"
        f"  DB rows updated: [bold]{updated}[/bold]\n"
        f"  Time:            {elapsed:.1f}s",
        border_style="green",
        title="Refresh complete",
    ))


if __name__ == "__main__":
    main()
