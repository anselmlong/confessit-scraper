import re
from collections import Counter

NUS_STOPWORDS = {
    "nus", "ntu", "smu", "university", "semester", "sem", "module", "mod",
    "the", "a", "an", "is", "it", "in", "to", "and", "of", "for", "that",
    "this", "i", "you", "he", "she", "they", "we", "my", "your", "his",
    "her", "our", "their", "with", "at", "on", "from", "by", "about",
    "was", "are", "were", "be", "been", "have", "has", "had", "do", "did",
    "not", "but", "or", "if", "so", "as", "up", "out", "no", "just",
    "can", "will", "would", "could", "should", "may", "might", "am",
    "me", "him", "us", "them", "what", "when", "where", "who", "how",
    "like", "very", "really", "also", "than", "then", "more", "some",
    "any", "all", "one", "time", "get", "got", "its", "even", "still",
}


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'http\S+|www\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'[^\w\s.,!?\'"-]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_metadata(message: dict) -> dict:
    from datetime import datetime
    msg = dict(message)
    text = msg.get("text", "") or ""
    msg["word_count"] = len(text.split())
    msg["char_count"] = len(text)

    date_str = msg.get("date", "")
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        msg["hour_of_day"] = dt.hour
        msg["day_of_week"] = dt.strftime("%A")
    except (ValueError, AttributeError):
        msg["hour_of_day"] = None
        msg["day_of_week"] = None

    return msg


def process_messages(messages: list[dict]) -> list[dict]:
    result = []
    for msg in messages:
        m = extract_metadata(msg)
        m["clean_text"] = clean_text(m.get("text", "") or "")
        result.append(m)
    return result


def get_daily_messages(messages: list[dict], date: str) -> list[dict]:
    return [m for m in messages if (m.get("date") or "").startswith(date)]


def get_top_words(messages: list[dict], top_n: int = 20, exclude_stopwords: bool = True) -> list[tuple]:
    words = []
    for msg in messages:
        text = (msg.get("clean_text") or msg.get("text") or "").lower()
        tokens = re.findall(r'\b[a-z]{3,}\b', text)
        if exclude_stopwords:
            tokens = [t for t in tokens if t not in NUS_STOPWORDS]
        words.extend(tokens)
    return Counter(words).most_common(top_n)
