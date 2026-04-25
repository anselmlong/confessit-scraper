#!/usr/bin/env python3
import argparse
import os
import re
import sys
from datetime import date, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from src.logger import setup_logging
from src.storage.db import init_db, get_messages
from src.analysis.processor import process_messages, get_daily_messages, get_top_words
from src.analysis.sentiment import analyze_messages, aggregate_sentiment, categorize_topics
from src.analysis.stats import compute_daily_stats
from src.analysis.visualizations import generate_all_charts
from src.reporting.report import generate_daily_report

console = Console()

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(value: str) -> str:
    if not _DATE_RE.match(value):
        raise argparse.ArgumentTypeError(
            f"Invalid date format {value!r}. Expected YYYY-MM-DD, e.g. 2025-04-20"
        )
    try:
        date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid calendar date: {value!r}")
    return value


def main():
    parser = argparse.ArgumentParser(
        description="Generate a daily NUSConfessIT digest report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python report.py                        # report for yesterday (default)
  python report.py --date 2025-04-20     # report for a specific date
  python report.py --no-charts           # skip chart generation (faster)
  python report.py --log-level DEBUG     # verbose output for debugging
        """,
    )
    parser.add_argument(
        "--date",
        default=str(date.today() - timedelta(days=1)),
        type=_validate_date,
        help="Date to report on in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument("--no-charts", action="store_true",
                        help="Skip chart generation")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging verbosity (default: INFO)")
    args = parser.parse_args()

    log = setup_logging(args.log_level)

    console.print(Panel.fit(
        f"[bold blue]NUSConfessIT Daily Digest[/bold blue]\n"
        f"[dim]Report date: {args.date}[/dim]",
        border_style="blue",
    ))

    # --- load messages ---
    try:
        init_db()
        all_messages = get_messages()
    except RuntimeError as e:
        console.print(f"[bold red]Database error:[/bold red] {e}")
        sys.exit(1)

    daily = get_daily_messages(all_messages, args.date)

    if not daily:
        console.print(
            f"[yellow]No messages found for {args.date}.[/yellow]\n"
            f"[dim]Run [bold]python scrape.py[/bold] to fetch messages first, "
            f"then try again.[/dim]"
        )
        sys.exit(0)

    log.info("Found %d messages for %s. Generating report...", len(daily), args.date)

    # --- analysis pipeline (with step-by-step status) ---
    with Status("[bold]Analysing sentiment...", console=console) as status:
        analyzed = analyze_messages(daily)
        sentiment_data = aggregate_sentiment(analyzed)
        log.debug("Sentiment: avg_compound=%.3f, pos=%.1f%%, neg=%.1f%%",
                  sentiment_data.get("avg_compound", 0),
                  sentiment_data.get("pct_positive", 0),
                  sentiment_data.get("pct_negative", 0))

        status.update("[bold]Classifying topics...")
        topic_data = categorize_topics(daily)
        log.debug("Topics: %s", topic_data.get("topic_counts"))

        status.update("[bold]Computing stats...")
        top_words = get_top_words(daily, top_n=20)
        stats = compute_daily_stats(daily)

        chart_paths = {}
        if not args.no_charts:
            status.update("[bold]Generating charts...")
            try:
                chart_paths = generate_all_charts(
                    args.date, daily, sentiment_data, topic_data, dict(top_words)
                )
            except Exception as e:
                log.warning("Chart generation partially failed: %s", e)
                console.print(f"[yellow]Warning:[/yellow] Some charts could not be generated: {e}")

        status.update("[bold]Rendering report...")
        try:
            html = generate_daily_report(
                args.date, daily, sentiment_data, topic_data, top_words, stats, chart_paths
            )
        except Exception as e:
            log.exception("Report rendering failed")
            console.print(f"[bold red]Failed to render report:[/bold red] {e}")
            sys.exit(1)

    # --- save report ---
    os.makedirs("reports", exist_ok=True)
    output_path = f"reports/{args.date}_digest.html"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
    except OSError as e:
        console.print(f"[bold red]Could not write report:[/bold red] {e}")
        sys.exit(1)

    top_topic = max(topic_data["topic_counts"], key=topic_data["topic_counts"].get,
                    default="—").replace("_", " ").title()
    mood = (
        "😊 Positive" if sentiment_data.get("avg_compound", 0) >= 0.05
        else "😢 Negative" if sentiment_data.get("avg_compound", 0) <= -0.05
        else "😐 Neutral"
    )

    console.print(Panel(
        f"[bold green]Report ready![/bold green]\n\n"
        f"  Messages:  [bold]{len(daily)}[/bold]\n"
        f"  Mood:      {mood}\n"
        f"  Top topic: [bold]{top_topic}[/bold]\n"
        f"  Charts:    {'[dim]skipped[/dim]' if args.no_charts else f'[bold]{len(chart_paths)}[/bold] generated'}\n\n"
        f"  [bold cyan]{output_path}[/bold cyan]",
        border_style="green",
        title="Done",
    ))
    log.info("Report saved to %s (%d messages, mood=%s)", output_path, len(daily), mood)


if __name__ == "__main__":
    main()
