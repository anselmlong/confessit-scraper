from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

TOPIC_KEYWORDS = {
    "academics": {"exam", "grade", "module", "lecture", "tutorial", "assignment", "prof",
                  "professor", "gpa", "cap", "test", "quiz", "study", "studying", "finals",
                  "midterm", "project", "essay", "deadline", "score", "result"},
    "social": {"friend", "friends", "relationship", "crush", "love", "date", "dating",
               "party", "club", "ccas", "cca", "social", "meet", "hang", "lonely"},
    "mental_health": {"stress", "stressed", "anxiety", "anxious", "depressed", "depression",
                      "lonely", "loneliness", "overwhelmed", "burnout", "tired", "exhausted",
                      "mental", "health", "sad", "unhappy", "helpless", "hopeless"},
    "accommodation": {"hall", "hostel", "pgp", "utown", "room", "residential", "dorm",
                      "college", "rc", "rvrc", "capt", "tembusu", "cinnamon", "raffles"},
    "career": {"internship", "intern", "job", "interview", "resume", "cv", "linkedin",
               "work", "company", "offer", "salary", "hire", "hiring", "career", "oa"},
    "food": {"canteen", "deck", "food", "eat", "eating", "lunch", "dinner", "breakfast",
             "makan", "hungry", "restaurant", "cafe", "drink"},
}


def analyze_sentiment(text: str) -> dict:
    if not text or not text.strip():
        return {"compound": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0, "label": "neutral"}
    scores = _analyzer.polarity_scores(text)
    compound = scores["compound"]
    label = "positive" if compound >= 0.05 else ("negative" if compound <= -0.05 else "neutral")
    return {
        "compound": round(compound, 4),
        "positive": round(scores["pos"], 4),
        "negative": round(scores["neg"], 4),
        "neutral": round(scores["neu"], 4),
        "label": label,
    }


def analyze_messages(messages: list[dict]) -> list[dict]:
    result = []
    for msg in messages:
        text = msg.get("clean_text") or msg.get("text") or ""
        sentiment = analyze_sentiment(text)
        result.append({**msg, **sentiment})
    return result


def aggregate_sentiment(analyzed: list[dict]) -> dict:
    if not analyzed:
        return {}
    compounds = [m["compound"] for m in analyzed]
    avg_compound = sum(compounds) / len(compounds)
    pos = sum(1 for m in analyzed if m["label"] == "positive")
    neg = sum(1 for m in analyzed if m["label"] == "negative")
    neu = sum(1 for m in analyzed if m["label"] == "neutral")
    total = len(analyzed)

    sorted_by_sentiment = sorted(analyzed, key=lambda m: m.get("compound", 0))
    most_negative = sorted_by_sentiment[0] if sorted_by_sentiment else None
    most_positive = sorted_by_sentiment[-1] if sorted_by_sentiment else None

    return {
        "avg_compound": round(avg_compound, 4),
        "pct_positive": round(pos / total * 100, 1),
        "pct_negative": round(neg / total * 100, 1),
        "pct_neutral": round(neu / total * 100, 1),
        "most_positive_msg": most_positive,
        "most_negative_msg": most_negative,
        "total": total,
    }


def categorize_topics(messages: list[dict]) -> dict:
    topic_msg_ids = {t: [] for t in TOPIC_KEYWORDS}

    for msg in messages:
        text = (msg.get("clean_text") or msg.get("text") or "").lower()
        words = set(text.split())
        for topic, keywords in TOPIC_KEYWORDS.items():
            if words & keywords:
                topic_msg_ids[topic].append(msg["id"])

    return {
        "topic": topic_msg_ids,
        "topic_counts": {t: len(ids) for t, ids in topic_msg_ids.items()},
    }
