#!/usr/bin/env python3
"""Scrape reply comments from the NUSConfessIT linked discussion group.

Usage:
  python scrape_replies.py                           # incremental (new replies only)
  python scrape_replies.py --backfill                # continue backfill (scrape older messages)
  python scrape_replies.py --limit 1000              # fetch at most 1000 replies
  python scrape_replies.py --since-msg-id 0          # refetch everything from beginning
  python scrape_replies.py --log-level DEBUG         # verbose output

Modes:
  Default (incremental) — uses get_latest_reply_msg_id() as min_id.
    Only fetches messages NEWER than what's in the DB. For daily cron.

  --backfill — uses get_earliest_reply_msg_id() as max_id.
    Continues scraping OLDER messages going backward in history.
    Safe to interrupt and resume — tracks progress via DB.

  --since-msg-id 0 + --backfill — full backfill from the very beginning.
"""

import argparse
import sys
import time

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

from src.logger import setup_logging
from src.scraper import scrape_replies
from src.storage.db import init_db, get_latest_reply_msg_id, get_earliest_reply_msg_id

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Scrape replies from the NUSConfessIT linked discussion group.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape_replies.py                       # incremental (daily cron)
  python scrape_replies.py --backfill            # continue scraping older messages
  python scrape_replies.py --since-msg-id 0      # re-fetch everything from the beginning
  python scrape_replies.py --limit 1000          # fetch at most 1000 replies
        """,
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of replies to fetch (default: all new)")
    parser.add_argument("--since-msg-id", type=int, default=None,
                        help="Fetch replies with message ID greater than this")
    parser.add_argument("--backfill", action="store_true",
                        help="Continue backfill: scrape messages OLDER than what's in DB")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging verbosity (default: INFO)")
    args = parser.parse_args()

    log = setup_logging(args.log_level)

    mode_str = "backfill (going backward)" if args.backfill else "incremental (new only)"
    console.print(Panel.fit(
        "[bold purple]NUSConfessIT Reply Scraper[/bold purple]\n"
        f"[dim]Mode: {mode_str} — Linked group: NUS ConfessIt chat[/dim]",
        border_style="purple",
    ))

    # --- initialise DB ---
    try:
        init_db()
    except RuntimeError as e:
        console.print(f"[bold red]Database error:[/bold red] {e}")
        sys.exit(1)

    # --- resolve IDs ---
    total_stored = get_latest_reply_msg_id() is not None

    if args.backfill:
        # Backfill: go OLDER. Use earliest reply_msg_id as max_id boundary.
        earliest = get_earliest_reply_msg_id()
        max_msg_id = earliest if earliest > 0 else 0
        since_msg_id = args.since_msg_id if args.since_msg_id is not None else 0
        if max_msg_id:
            console.print(f"[dim]Backfill resume: scraping messages older than msg ID {max_msg_id}[/dim]")
        else:
            console.print("[dim]Full backfill: no existing replies in database[/dim]")
    else:
        # Incremental: go NEWER. Use latest reply_msg_id as min_id boundary.
        max_msg_id = 0
        since_msg_id = args.since_msg_id if args.since_msg_id is not None else get_latest_reply_msg_id()
        if since_msg_id:
            console.print(f"[dim]Incremental: only replies newer than msg ID {since_msg_id}[/dim]")
        else:
            console.print("[dim]Incremental: no existing replies, fetching from newest[/dim]")

    # --- scrape ---
    start = time.monotonic()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[bold purple]{task.fields[count]}[/bold purple] replies"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching replies...", total=None, count=0)

        try:
            total_saved = scrape_replies(
                limit=args.limit,
                since_msg_id=since_msg_id,
                max_msg_id=max_msg_id,
                progress_callback=lambda n: progress.update(task, count=n),
            )
        except ValueError as e:
            console.print(f"\n[bold red]Configuration error:[/bold red]\n{e}")
            sys.exit(1)
        except RuntimeError as e:
            console.print(f"\n[bold red]Error:[/bold red]\n{e}")
            log.exception("Reply scrape failed")
            sys.exit(2)
        except KeyboardInterrupt:
            console.print("\n[yellow]Scrape interrupted by user.[/yellow]")
            sys.exit(0)

    elapsed = time.monotonic() - start

    if not total_saved:
        console.print("[yellow]No new replies found — database is already up to date.[/yellow]")
        return

    console.print(Panel(
        f"[bold green]Done![/bold green]\n\n"
        f"  Saved:    [bold]{total_saved}[/bold] new replies\n"
        f"  Time:     {elapsed:.1f}s\n\n"
        "[dim]Replies stored in the [bold]replies[/bold] table.[/dim]",
        border_style="green",
        title="Reply scrape complete",
    ))
    log.info("Reply scrape complete: %d saved in %.1fs", total_saved, elapsed)


if __name__ == "__main__":
    main()