import os
import base64
from io import BytesIO


def _fig_to_base64(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _save_or_b64(fig, output_path: str) -> str:
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        return output_path
    return _fig_to_base64(fig)


def plot_sentiment_pie(sentiment_data: dict, output_path: str = None) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 4))
    labels = ["Positive", "Neutral", "Negative"]
    sizes = [sentiment_data.get("pct_positive", 0), sentiment_data.get("pct_neutral", 0), sentiment_data.get("pct_negative", 0)]
    colors = ["#4CAF50", "#9E9E9E", "#F44336"]
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
    ax.set_title("Sentiment Breakdown")
    result = _save_or_b64(fig, output_path)
    plt.close(fig)
    return result


def plot_hourly_heatmap(hourly_dist: dict, output_path: str = None) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    fig, ax = plt.subplots(figsize=(10, 4))
    hours = list(range(24))
    counts = [hourly_dist.get(h, 0) for h in hours]
    sns.barplot(x=hours, y=counts, palette="Blues_d", ax=ax)
    ax.set_xlabel("Hour of Day (UTC+8)")
    ax.set_ylabel("Number of Confessions")
    ax.set_title("Posting Activity by Hour")
    result = _save_or_b64(fig, output_path)
    plt.close(fig)
    return result


def plot_topic_bar(topic_counts: dict, output_path: str = None) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    fig, ax = plt.subplots(figsize=(8, 4))
    topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    names = [t[0].replace("_", " ").title() for t in topics]
    vals = [t[1] for t in topics]
    sns.barplot(x=vals, y=names, palette="YlOrBr", ax=ax, orient="h")
    ax.set_xlabel("Number of Confessions")
    ax.set_title("Hot Topics Today")
    result = _save_or_b64(fig, output_path)
    plt.close(fig)
    return result


def plot_wordcloud(word_freq: dict, output_path: str = None) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from wordcloud import WordCloud
    if not word_freq:
        return ""
    wc = WordCloud(width=800, height=400, background_color="white",
                   colormap="Blues", max_words=50).generate_from_frequencies(word_freq)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title("Word Cloud")
    result = _save_or_b64(fig, output_path)
    plt.close(fig)
    return result


def generate_all_charts(date: str, messages: list, sentiment_data: dict,
                        topic_data: dict, top_words: dict) -> dict:
    charts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "reports", "charts", date
    )
    os.makedirs(charts_dir, exist_ok=True)

    result = {}
    if sentiment_data:
        result["sentiment_pie"] = plot_sentiment_pie(sentiment_data, os.path.join(charts_dir, "sentiment.png"))

    if messages:
        from .stats import compute_daily_stats
        stats = compute_daily_stats(messages)
        hourly = stats.get("hourly_distribution", {})
        if hourly:
            result["hourly"] = plot_hourly_heatmap(hourly, os.path.join(charts_dir, "hourly.png"))

    if topic_data and topic_data.get("topic_counts"):
        result["topics"] = plot_topic_bar(topic_data["topic_counts"], os.path.join(charts_dir, "topics.png"))

    if top_words:
        result["wordcloud"] = plot_wordcloud(top_words, os.path.join(charts_dir, "wordcloud.png"))

    return result
