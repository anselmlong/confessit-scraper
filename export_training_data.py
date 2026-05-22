#!/usr/bin/env python3
"""Export top confession posts from SQLite → JSONL for Unsloth fine-tuning.

Filters to posts with reply_count >= 6 (top ~10k by engagement),
extracts clean body text, strips bot template footers, and outputs
causal LM format: {"text": "..."} per line.
"""

import sqlite3
import json
import re
import argparse
from pathlib import Path


# Patterns for the bot template footer that gets appended to posts
_TEMPLATE_LINES = re.compile(
    r"^(?:"                                      # start of line
    r"[✍🫣😆👇]\s*"                             # leading emoji
    r"(?:\[?\*\*)?(?:Click here|Send an)"        # "Click here" or "Send an"
    r".*"                                        # rest of the line
    r")",
    re.MULTILINE,
)

# Patterns for lines that are part of the template footer
_TEMPLATE_MARKERS = [
    "Click here",
    "NUSConfessIT_bot",
    "👇 Comment **below** anonymously",
    "😆 Send an **anonymous message**",
    "Send an **anonymous message**",
    "PM THIS",
    "PM Confessor",
    "post a confession",
    "post **YOUR OWN** confession",
    "post your own anonymous",
]


def _is_template_line(line: str) -> bool:
    """Check if a line is bot template boilerplate."""
    stripped = line.strip()
    if not stripped:
        return False
    return any(marker in stripped for marker in _TEMPLATE_MARKERS)


def clean_body(text: str) -> str | None:
    """
    Strip bot template footer from post text.
    Returns None if the text is ONLY template (filter it out).
    """
    if not text:
        return None

    lines = text.strip().split("\n")

    # Find where template section starts (first line that matches template patterns)
    template_start = None
    for i, line in enumerate(lines):
        if _is_template_line(line):
            template_start = i
            break

    if template_start is None:
        # No template found — return as-is
        return text.strip()

    # If the template starts at line 0, the whole thing is template
    if template_start == 0:
        return None

    # There's real content before the template — strip the template
    body = "\n".join(lines[:template_start]).strip()
    return body if body else None


def export(
    db_path: str,
    output: str,
    min_replies: int = 6,
    limit: int = 10_000,
    min_chars: int = 20,
    max_chars: int = 2000,
):
    conn = sqlite3.connect(db_path)

    # Use content column (clean body) if available, fall back to text (has metadata)
    rows = conn.execute(
        """
        SELECT
            COALESCE(NULLIF(content, ''), NULLIF(text, '')) AS body,
            reply_count
        FROM messages
        WHERE reply_count >= ?
          AND COALESCE(NULLIF(content, ''), NULLIF(text, '')) IS NOT NULL
        ORDER BY reply_count DESC
        LIMIT ?
        """,
        (min_replies, limit * 3),  # over-fetch to account for filtered noise
    ).fetchall()

    total = 0
    filtered_noise = 0
    with open(output, "w", encoding="utf-8") as f:
        for body, reply_count in rows:
            clean = clean_body(body)
            if clean is None:
                filtered_noise += 1
                continue

            if len(clean) < min_chars or len(clean) > max_chars:
                continue

            # Noise filter: skip if mostly non-alphabetic (links, spam)
            alpha_ratio = sum(c.isalpha() for c in clean) / max(len(clean), 1)
            if alpha_ratio < 0.3:
                filtered_noise += 1
                continue

            f.write(json.dumps({"text": clean}, ensure_ascii=False) + "\n")
            total += 1

            if total >= limit:
                break

    conn.close()
    print(f"Exported {total} posts to {output}")
    print(f"  Filtered out {filtered_noise} noise entries (template-only / spam)")

    if total:
        # Re-read for length stats
        with open(output) as f:
            lengths = [len(json.loads(l)["text"]) for l in f]
        lengths.sort()
        print(
            f"  Length -> min: {lengths[0]}  |  max: {lengths[-1]}  |  "
            f"median: {lengths[len(lengths)//2]}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export confessions for fine-tuning")
    parser.add_argument(
        "--db",
        default=str(Path(__file__).parent / "data" / "messages.db"),
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent / "data" / "confessions.jsonl"),
        help="Output JSONL path",
    )
    parser.add_argument("--min-replies", type=int, default=6, help="Min reply count filter")
    parser.add_argument("--limit", type=int, default=10_000, help="Max posts to export")
    parser.add_argument("--min-chars", type=int, default=20, help="Min text length filter")
    parser.add_argument("--max-chars", type=int, default=2000, help="Max text length filter")
    args = parser.parse_args()

    export(
        db_path=args.db,
        output=args.output,
        min_replies=args.min_replies,
        limit=args.limit,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
    )