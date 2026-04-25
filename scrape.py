#!/usr/bin/env python3
import argparse
import sys
from rich.console import Console
from src.scraper import scrape_channel
from src.storage.db import init_db, save_messages, get_latest_id
from src.analysis.processor import process_messages

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Scrape NUSConfessIT Telegram channel")
    parser.add_argument("--channel", default="https://t.me/NUSConfessIT")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--since-id",
        type=int,
        default=None,
        help="Fetch messages newer than this ID. Defaults to latest in DB.",
    )
    args = parser.parse_args()

    init_db()
    since_id = args.since_id if args.since_id is not None else get_latest_id()

    console.print(f"[bold blue]Scraping {args.channel} (since_id={since_id})...[/bold blue]")

    try:
        raw_messages = scrape_channel(args.channel, limit=args.limit, since_id=since_id)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    if not raw_messages:
        console.print("[yellow]No new messages found.[/yellow]")
        return

    messages = process_messages(raw_messages)
    save_messages(messages)
    console.print(f"[bold green]Saved {len(messages)} messages to database.[/bold green]")


if __name__ == "__main__":
    main()
