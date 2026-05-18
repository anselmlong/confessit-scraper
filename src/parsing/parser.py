"""
Structured confession parser.

Extracts category, confession ID, title, and content from the
NUSConfessIT Telegram confession format:

    **#Category** 📚: __TITLE__

    **ID:** #CONFESSIONID
    ---
    content text
    ---
"""

import re
from src.logger import get_logger

log = get_logger("parser")

# The header line: **#Category** optional_emoji: __TITLE__ optional_emoji
_HEADER_RE = re.compile(
    r"\*\*#?\s*(?P<category>[^*\n]+?)\s*\*\*"  # **#Category** or **Category**
    r"(?:\s*[^\w\s]*)?"                          # optional emoji / symbols
    r"\s*:\s*"                                    # colon separator
    r"(?:_{1,2})?"                                # optional __ or _ prefix
    r"(?P<title>[^\n]+?)"                         # title text
    r"(?:_{1,2})?"                                # optional __ or _ suffix
    r"(?:\s*[^\w\s]*)?$",                         # optional trailing emoji
    re.MULTILINE,
)

_ID_RE = re.compile(r"\*\*ID:\*\*\s*#?(?P<confession_id>[A-Za-z0-9]+)")

_SEP_RE = re.compile(r"^---\s*$", re.MULTILINE)


def parse_confession(text: str) -> dict[str, str | None]:
    """Parse a single confession message into structured fields.

    Returns a dict with keys: category, confession_id, title, content.
    Values are None if the field couldn't be extracted.
    """
    if not text:
        return _empty_result()

    result: dict[str, str | None] = {
        "category": None,
        "confession_id": None,
        "title": None,
        "content": None,
    }

    # --- extract header (category + title) ---
    header_match = _HEADER_RE.search(text)
    if header_match:
        cat = header_match.group("category").strip().lstrip("#")
        result["category"] = cat if cat else None
        t = header_match.group("title").strip()
        # strip trailing emojis and markdown
        t = re.sub(r"[^\w\s.,!?;:'\"()\-—/&]", "", t).strip()
        result["title"] = t if t else None
        log.debug("Parsed header: category=%s, title=%s", result["category"], result["title"])

    # --- extract confession ID ---
    id_match = _ID_RE.search(text)
    if id_match:
        result["confession_id"] = id_match.group("confession_id").upper()
        log.debug("Parsed confession_id=%s", result["confession_id"])

    # --- extract content between --- separators ---
    parts = _SEP_RE.split(text)
    if len(parts) >= 3:
        # content sits between first and last ---
        content = "\n".join(p.strip() for p in parts[1:-1] if p.strip())
        result["content"] = content if content else None
    elif len(parts) == 2:
        # single --- separator: content is after it
        content = parts[1].strip()
        result["content"] = content if content else None
    else:
        # no separators: use everything after the ID line as content
        id_pos = text.find("**ID:**")
        if id_pos >= 0:
            after_id = text[id_pos:].split("\n", 1)
            if len(after_id) > 1:
                content = after_id[1].strip()
                result["content"] = content if content else None

    log.debug("Parsed confession: %s", {k: (v[:50] + "..." if v and len(v) > 50 else v) for k, v in result.items()})
    return result


def parse_batch(messages: list[dict]) -> list[dict]:
    """Parse a batch of messages, adding parsed fields to each."""
    parsed = 0
    for msg in messages:
        text = msg.get("text", "") or ""
        fields = parse_confession(text)
        msg["category"] = fields["category"]
        msg["confession_id"] = fields["confession_id"]
        msg["title"] = fields["title"]
        msg["content"] = fields["content"]
        if fields["category"] or fields["confession_id"]:
            parsed += 1
    if messages:
        log.info("Parsed %d/%d messages successfully (%.0f%%)", parsed, len(messages),
                 parsed / len(messages) * 100)
    return messages


def _empty_result() -> dict[str, str | None]:
    return {"category": None, "confession_id": None, "title": None, "content": None}
