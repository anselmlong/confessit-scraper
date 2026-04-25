import base64
import os
from datetime import date, timedelta
from jinja2 import Environment, FileSystemLoader


def _build_tldr(sentiment_data: dict, topic_data: dict) -> list[str]:
    bullets = []
    avg_compound = sentiment_data.get("avg_compound", 0)
    pct_negative = sentiment_data.get("pct_negative", 0)
    pct_positive = sentiment_data.get("pct_positive", 0)
    topic_counts = topic_data.get("topic_counts", {})

    if pct_negative > 40:
        bullets.append("Students are venting heavily today — high stress vibes.")
    if topic_counts.get("mental_health", 0) > 3:
        bullets.append("Mental health struggles featured prominently.")

    top_topic = max(topic_counts, key=topic_counts.get) if topic_counts else None
    if top_topic == "academics":
        bullets.append("Academics dominating the conversation — exam season energy.")
    elif top_topic == "social":
        bullets.append("Social life and relationships in the spotlight.")
    elif top_topic == "career":
        bullets.append("Career anxiety in the air — internship hunt season.")
    elif top_topic == "mental_health":
        bullets.append("Mental health is the talk of the day — check on your friends.")
    elif top_topic == "accommodation":
        bullets.append("Hall life and accommodation issues trending today.")
    elif top_topic == "food":
        bullets.append("Food and canteen talk is fuelling the feed today.")

    if avg_compound > 0.2:
        bullets.append("Overall positive energy today — good vibes!")
    elif avg_compound < -0.2:
        bullets.append("The mood is heavy today — lots of frustration and stress.")

    if pct_positive > 50:
        bullets.append("More than half the posts are upbeat — rare and refreshing.")

    if not bullets:
        bullets.append("A mixed bag today — scroll down for the highlights.")

    return bullets


def _embed_chart(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"


def generate_daily_report(
    report_date: str,
    messages: list[dict],
    sentiment_data: dict,
    topic_data: dict,
    top_words: list[tuple],
    stats: dict,
    chart_paths: dict,
) -> str:
    tldr = _build_tldr(sentiment_data, topic_data)

    charts_b64 = {}
    for key, path in chart_paths.items():
        charts_b64[key] = _embed_chart(path)

    highlights = []
    if sentiment_data.get("most_positive_msg"):
        highlights.append({"label": "Most Positive", "msg": sentiment_data["most_positive_msg"]})
    if sentiment_data.get("most_negative_msg"):
        highlights.append({"label": "Most Negative", "msg": sentiment_data["most_negative_msg"]})

    topic_counts = topic_data.get("topic_counts", {})
    top_topic = max(topic_counts, key=topic_counts.get) if topic_counts else None

    hourly_dist = stats.get("hourly_distribution", {})
    peak_hour = max(hourly_dist, key=hourly_dist.get) if hourly_dist else None
    max_hourly = max(hourly_dist.values(), default=1) or 1

    template_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "reports",
    )
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template("template.html")

    return template.render(
        report_date=report_date,
        tldr=tldr,
        stats=stats,
        sentiment_data=sentiment_data,
        topic_counts=topic_counts,
        top_topic=top_topic,
        top_words=top_words,
        highlights=highlights,
        hourly_dist=hourly_dist,
        peak_hour=peak_hour,
        max_hourly=max_hourly,
        charts=charts_b64,
        total_messages=len(messages),
    )
