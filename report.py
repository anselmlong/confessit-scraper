#!/usr/bin/env python3
import argparse
from datetime import date, timedelta
from rich.console import Console
from src.storage.db import init_db, get_messages
from src.analysis.processor import process_messages, get_daily_messages, get_top_words
from src.analysis.sentiment import analyze_messages, aggregate_sentiment, categorize_topics
from src.analysis.stats import compute_daily_stats
from src.analysis.visualizations import generate_all_charts
from src.reporting.report import generate_daily_report

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Generate NUSConfessIT daily digest report")
    parser.add_argument(
        "--date",
        default=str(date.today() - timedelta(days=1)),
        help="Date to report on (YYYY-MM-DD). Defaults to yesterday.",
    )
    parser.add_argument("--no-charts", action="store_true", help="Skip chart generation")
    args = parser.parse_args()

    init_db()
    all_messages = get_messages()
    daily = get_daily_messages(all_messages, args.date)

    if not daily:
        console.print(f"[yellow]No messages found for {args.date}. Run scrape.py first.[/yellow]")
        return

    console.print(f"[bold blue]Generating report for {args.date} ({len(daily)} messages)...[/bold blue]")

    analyzed = analyze_messages(daily)
    sentiment_data = aggregate_sentiment(analyzed)
    topic_data = categorize_topics(daily)
    top_words = get_top_words(daily, top_n=20)
    stats = compute_daily_stats(daily)

    chart_paths = {}
    if not args.no_charts:
        chart_paths = generate_all_charts(args.date, daily, sentiment_data, topic_data, dict(top_words))

    html = generate_daily_report(args.date, daily, sentiment_data, topic_data, top_words, stats, chart_paths)

    output_path = f"reports/{args.date}_digest.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    console.print(f"[bold green]Report saved to {output_path}[/bold green]")


if __name__ == "__main__":
    main()
