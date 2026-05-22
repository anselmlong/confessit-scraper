"""Structured confession parser.

Extracts category, confession ID, title, and content from the
NUSConfessIT Telegram confession format.

Two formats:

Format A (early, Feb–Apr 2024):
    **Category:** #Category 📚
    **ID:** #CONFESSIONID           (or **Confession ID:** #CONFESSIONID)
    **Message:**
    content here
    ---
    [footer template]

Format B (modern, Apr 2024+):
    **#Category** 📚: __TITLE__
    **ID:** #CONFESSIONID
    ---
    content here
    ---
    [footer template]
"""

import re
from src.logger import get_logger

log = get_logger("parser")

# Format A header: **Category:** #Category 📚
_FMT_A_HEADER_RE = re.compile(
    r"\*\*Category:\*\*\s*#?\s*(?P<category>[^\n]+?)\s*$",
    re.MULTILINE,
)

# Format A title line: **Message:**
_FMT_A_MESSAGE_RE = re.compile(r"^\*\*Message:\*\*\s*$", re.MULTILINE)

# Format B header: **#Category** 📚: __TITLE__
_FMT_B_HEADER_RE = re.compile(
    r"\*\*#?\s*(?P<category>[^*\n]+?)\s*\*+"  # **#Category** or **Category**  (handles **** double asterisk)
    r"(?:\s*[^\w\s]*)?"                          # optional emoji / symbols
    r"\s*:\s*"                                    # colon separator
    r"(?:_{1,2})?"                                # optional __ or _ prefix
    r"(?P<title>[^\n]+?)"                         # title text
    r"(?:_{1,2})?"                                # optional __ or _ suffix
    r"(?:\s*[^\w\s]*)?$",                         # optional trailing emoji
    re.MULTILINE,
)

# ID: **ID:** #XXX or **Confession ID:** #XXX
_FMT_A_ID_RE = re.compile(r"\*\*Confession ID:\*\*\s*#?(?P<confession_id>[A-Za-z0-9]+)")
_FMT_B_ID_RE = re.compile(r"\*\*ID:\*\*\s*#?(?P<confession_id>[A-Za-z0-9]+)")

_SEP_RE = re.compile(r"^---\s*$", re.MULTILINE)

# Footer boilerplate markers — lines that signal the end of confession content
_FOOTER_MARKERS = [
    "Click here", "NUSConfessIT_bot",
    "👇 Comment **below** anonymously", "😆 Send an **anonymous message**",
    "Send an **anonymous message**", "PM THIS", "PM Confessor",
    "post a confession", "post **YOUR OWN** confession",
    "post your own anonymous", "Help us sustain",
    "donate.stripe.com",
]


def _is_footer_start(line: str) -> bool:
    s = line.strip()
    return bool(s) and any(m in s for m in _FOOTER_MARKERS)


def _strip_footer(text: str) -> str | None:
    """Remove footer boilerplate from confession text."""
    if not text:
        return None
    lines = text.strip().split("\n")
    for i, line in enumerate(lines):
        if _is_footer_start(line):
            if i == 0:
                return None  # whole thing is footer
            return "\n".join(lines[:i]).strip() or None
    return text.strip() or None


def _extract_title_from_message(text: str) -> str | None:
    """For Format A: extract the first meaningful line after **Message:**."""
    m = _FMT_A_MESSAGE_RE.search(text)
    if not m:
        return None
    after = text[m.end():].strip()
    # Take the first non-empty line up to --- or footer
    lines = after.split("\n")
    title_lines = []
    for line in lines:
        if _is_footer_start(line) or line.strip() == "---":
            break
        title_lines.append(line)
    if not title_lines:
        return None
    title = title_lines[0].strip()
    # Clean emojis and markdown
    title = re.sub(r"[^\w\s.,!?;:'\"()\-—/&]", "", title).strip()
    return title if title else None


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

    is_format_a = bool(re.search(r"^\*\*Category:\*\*", text, re.MULTILINE))

    # --- extract header (category + title) ---
    if is_format_a:
        m = _FMT_A_HEADER_RE.search(text)
        if m:
            cat = m.group("category").strip().lstrip("#")
            result["category"] = cat if cat else None
            result["title"] = _extract_title_from_message(text)
            log.debug("Format A: category=%s, title=%s", result["category"], result["title"])
    else:
        m = _FMT_B_HEADER_RE.search(text)
        if m:
            cat = m.group("category").strip().lstrip("#")
            result["category"] = cat if cat else None
            t = m.group("title").strip()
            t = re.sub(r"[^\w\s.,!?;:'\"()\-—/&]", "", t).strip()
            result["title"] = t if t else None
            log.debug("Format B: category=%s, title=%s", result["category"], result["title"])

    # --- extract confession ID ---
    m = _FMT_A_ID_RE.search(text) or _FMT_B_ID_RE.search(text)
    if m:
        result["confession_id"] = m.group("confession_id").upper()
        log.debug("Parsed confession_id=%s", result["confession_id"])

    # --- extract content ---
    parts = _SEP_RE.split(text)
    if len(parts) >= 3 and not is_format_a:
        # Format B: content between first and last ---
        content = "\n".join(p.strip() for p in parts[1:-1] if p.strip())
    else:
        # Format A or edge case: extract from **Message:** forward
        if is_format_a:
            msg_m = _FMT_A_MESSAGE_RE.search(text)
            if msg_m:
                raw_content = text[msg_m.end():].strip()
                # Split by first ---, take content before it
                segs = _SEP_RE.split(raw_content, maxsplit=1)
                content = segs[0].strip() if segs else raw_content
                content = _strip_footer(content)
            else:
                # Fallback: take everything after ID line, strip footer
                text_after_id = text
                id_pos = -1
                for label in ["**Confession ID:**", "**ID:**"]:
                    pos = text.find(label)
                    if pos >= 0:
                        id_pos = pos
                        break
                if id_pos >= 0:
                    after_id = text[id_pos:].split("\n", 1)
                    text_after_id = after_id[1] if len(after_id) > 1 else ""
                content = _strip_footer(text_after_id)
        else:
            # No separators, unknown format — try stripping footer from body
            text_after_id = text
            for label in ["**ID:**", "**Confession ID:**"]:
                pos = text.find(label)
                if pos >= 0:
                    after_id = text[pos:].split("\n", 1)
                    text_after_id = after_id[1] if len(after_id) > 1 else ""
                    break
            content = _strip_footer(text_after_id)

    if content:
        # Remove any remaining footer lines
        content = _strip_footer(content)
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
