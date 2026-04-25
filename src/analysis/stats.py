from collections import Counter
import statistics


def compute_daily_stats(messages: list[dict]) -> dict:
    if not messages:
        return {}

    word_counts = [m.get("word_count", 0) for m in messages]
    hourly = Counter(m.get("hour_of_day") for m in messages if m.get("hour_of_day") is not None)
    dow = Counter(m.get("day_of_week") for m in messages if m.get("day_of_week"))

    total_views = sum(m.get("views", 0) for m in messages)
    total_forwards = sum(m.get("forwards", 0) for m in messages)
    reactions = [m.get("reactions_count", 0) for m in messages]
    replies = sum(1 for m in messages if m.get("is_reply"))

    engagement = (total_views * 0.001 + total_forwards * 0.5 + sum(reactions) * 0.3) / max(len(messages), 1)

    return {
        "total_count": len(messages),
        "avg_word_count": round(sum(word_counts) / len(word_counts), 1) if word_counts else 0,
        "median_word_count": statistics.median(word_counts) if word_counts else 0,
        "total_views": total_views,
        "total_forwards": total_forwards,
        "hourly_distribution": dict(hourly),
        "day_of_week_distribution": dict(dow),
        "reply_rate": round(replies / len(messages), 3),
        "avg_reactions": round(sum(reactions) / len(reactions), 2) if reactions else 0,
        "engagement_score": round(engagement, 2),
    }


def compute_trends(messages_by_date: dict) -> dict:
    dates = sorted(messages_by_date.keys())
    counts = [len(messages_by_date[d]) for d in dates]

    def rolling_avg(values, window=7):
        result = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            result.append(sum(values[start:i+1]) / (i - start + 1))
        return result

    return {
        "dates": dates,
        "counts": counts,
        "moving_avg_count": rolling_avg(counts),
    }


def top_engaged_messages(messages: list[dict], top_n: int = 5) -> list[dict]:
    scored = []
    for m in messages:
        score = m.get("views", 0) * 0.001 + m.get("forwards", 0) * 2 + m.get("reactions_count", 0) * 3
        scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:top_n]]
