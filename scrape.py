#!/usr/bin/env python3
import argparse
import sys
import time

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import print as rprint

from src.logger import setup_logging
from src.scraper import scrape_channel
from src.storage.db import init_db, save_messages, get_latest_id
from src.analysis.processor import process_messages

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Scrape NUSConfessIT Telegram channel into a local database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape.py                          # incremental fetch (new messages only)
  python scrape.py --limit 500             # fetch at most 500 new messages
  python scrape.py --since-id 0            # re-fetch everything from the beginning
  python scrape.py --log-level DEBUG       # verbose output for debugging
        """,
    )
    parser.add_argument("--channel", default="https://t.me/NUSConfessIT",
                        help="Telegram channel URL (default: NUSConfessIT)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of messages to fetch (default: all new)")
    parser.add_argument("--since-id", type=int, default=None,
                        help="Fetch messages with ID greater than this (default: latest in DB)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging verbosity (default: INFO)")
    args = parser.parse_args()

    log = setup_logging(args.log_level)

    console.print(Panel.fit(
        "[bold blue]NUSConfessIT Scraper[/bold blue]\n"
        f"[dim]Channel: {args.channel}[/dim]",
        border_style="blue",
    ))

    # --- initialise DB ---
    try:
        init_db()
    except RuntimeError as e:
        console.print(f"[bold red]Database error:[/bold red] {e}")
        sys.exit(1)

    since_id = args.since_id if args.since_id is not None else get_latest_id()
    if since_id:
        console.print(f"[dim]Incremental fetch: only messages newer than ID {since_id}[/dim]")
    else:
        console.print("[dim]Full fetch: no existing messages in database[/dim]")

    # --- scrape with live counter ---
    fetched_count = [0]

    def on_progress(n: int):
        fetched_count[0] = n

    start = time.monotonic()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[bold blue]{task.fields[count]}[/bold blue] messages"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching...", total=None, count=0)

        try:
            raw_messages = scrape_channel(
                args.channel,
                limit=args.limit,
                since_id=since_id,
                progress_callback=lambda n: progress.update(task, count=n),
            )
        except ValueError as e:
            console.print(f"\n[bold red]Configuration error:[/bold red]\n{e}")
            sys.exit(1)
        except RuntimeError as e:
            console.print(f"\n[bold red]Error:[/bold red]\n{e}")
            log.exception("Scrape failed")
            sys.exit(2)
        except KeyboardInterrupt:
            console.print("\n[yellow]Scrape interrupted by user.[/yellow]")
            sys.exit(0)

    elapsed = time.monotonic() - start

    if not raw_messages:
        console.print("[yellow]No new messages found — database is already up to date.[/yellow]")
        return

    # --- process and save ---
    messages = process_messages(raw_messages)

    try:
        saved = save_messages(messages)
    except RuntimeError as e:
        console.print(f"[bold red]Failed to save messages:[/bold red] {e}")
        log.exception("DB save failed")
        sys.exit(1)

    console.print(Panel(
        f"[bold green]Done![/bold green]\n\n"
        f"  Fetched:  [bold]{len(raw_messages)}[/bold] messages\n"
        f"  Saved:    [bold]{saved}[/bold] new/updated rows\n"
        f"  Time:     {elapsed:.1f}s\n\n"
        "[dim]Run [bold]python report.py[/bold] to generate today's digest.[/dim]",
        border_style="green",
        title="Scrape complete",
    ))
    log.info("Scrape complete: %d fetched, %d saved in %.1fs", len(raw_messages), saved, elapsed)


if __name__ == "__main__":
    main()
