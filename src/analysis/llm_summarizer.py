"""
LLM-powered daily digest summarizer.

Uses OpenAI (GPT-4o-mini) to generate a 3-5 bullet summary of
the day's confessions — themes, vibe, notable patterns.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

from src.logger import get_logger

load_dotenv()
log = get_logger("summarizer")

_client: OpenAI | None = None
MAX_CHARS = 8000  # stay well under token limit for gpt-4o-mini


def _get_client() -> OpenAI | None:
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        log.warning("OPENAI_API_KEY not set — LLM summarization disabled")
        return None
    _client = OpenAI(api_key=api_key)
    return _client


def summarize_day(messages: list[dict]) -> str | None:
    """Generate a 3-5 bullet summary of the day's confessions.

    Returns None if summarization is unavailable or fails.
    """
    client = _get_client()
    if not client:
        return None

    if not messages:
        return None

    # build prompt content — prefer parsed content, fall back to text
    content_parts: list[str] = []
    for m in messages:
        title = m.get("title") or ""
        content = m.get("content") or m.get("clean_text") or m.get("text") or ""
        text = f"{title}: {content}" if title else content
        # truncate individual messages to ~500 chars
        content_parts.append(text[:500])

    full_content = "\n\n".join(content_parts)

    # truncate to stay under token budget
    if len(full_content) > MAX_CHARS:
        full_content = full_content[:MAX_CHARS] + "\n\n[... more confessions truncated ...]"
        log.debug("Truncated confession content to %d chars", MAX_CHARS)

    log.info("Generating LLM summary for %d messages (%d chars)...", len(messages), len(full_content))

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a campus vibe analyst for NUS (National University of Singapore). "
                        "Summarise today's anonymous student confessions in 3-5 bullets. "
                        "Focus on: dominant themes/moods, recurring complaints or celebrations, "
                        "anything surprising or funny. Keep it casual, student-perspective, "
                        "slightly witty. Each bullet one sentence max. Don't use markdown. "
                        "If the day seems quiet or boring, say so — don't force drama."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Here are today's confessions from NUS students. Summarise the vibe:\n\n{full_content}",
                },
            ],
            max_tokens=300,
            temperature=0.7,
        )
        summary = response.choices[0].message.content
        if summary:
            summary = summary.strip()
            log.info("LLM summary generated (%d chars)", len(summary))
        return summary
    except Exception as e:
        log.warning("LLM summarization failed: %s", e)
        return None
