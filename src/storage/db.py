import sqlite3
import os
from datetime import datetime

from src.logger import get_logger

log = get_logger("storage")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "messages.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    try:
        conn = _connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                date TEXT,
                text TEXT,
                views INTEGER DEFAULT 0,
                forwards INTEGER DEFAULT 0,
                reactions_count INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                is_reply BOOLEAN DEFAULT 0,
                reply_to_msg_id INTEGER,
                word_count INTEGER DEFAULT 0,
                char_count INTEGER DEFAULT 0,
                scraped_at TEXT,
                PRIMARY KEY (id, channel)
            )
        """)
        # v2 migration: add structured confession fields
        _migrate_v2(conn)
        # v3 migration: add replies table
        _migrate_v3(conn)
        conn.commit()
        conn.close()
        log.debug("Database initialised at %s", DB_PATH)
    except sqlite3.Error as e:
        raise RuntimeError(
            f"Failed to initialise database at {DB_PATH}: {e}\n"
            "Check that the data/ directory is writable."
        ) from e


def _migrate_v3(conn: sqlite3.Connection):
    """Add replies table for linked group comments (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            linked_parent_id INTEGER,
            reply_msg_id INTEGER NOT NULL,
            date TEXT,
            text TEXT,
            author TEXT,
            reactions_up INTEGER DEFAULT 0,
            reactions_down INTEGER DEFAULT 0,
            scraped_at TEXT,
            UNIQUE(reply_msg_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_replies_post_id ON replies(post_id)
    """)
    log.info("Migration v3: replies table created")


def _migrate_v2(conn: sqlite3.Connection):
    """Add structured confession columns (idempotent)."""
    for col, col_type in [
        ("category", "TEXT"),
        ("confession_id", "TEXT"),
        ("title", "TEXT"),
        ("content", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {col_type}")
            log.info("Migration: added column %s to messages", col)
        except sqlite3.OperationalError:
            pass  # column already exists


def save_messages(messages: list[dict], channel: str = "NUSConfessIT") -> int:
    if not messages:
        return 0
    try:
        conn = _connect()
        now = datetime.utcnow().isoformat()
        inserted = 0
        for msg in messages:
            cursor = conn.execute("""
                INSERT INTO messages (id, channel, date, text, views, forwards, reactions_count,
                    reply_count, is_reply, reply_to_msg_id, word_count, char_count, scraped_at,
                    category, confession_id, title, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id, channel) DO UPDATE SET
                    views=excluded.views,
                    forwards=excluded.forwards,
                    reactions_count=excluded.reactions_count,
                    reply_count=excluded.reply_count,
                    scraped_at=excluded.scraped_at,
                    category=excluded.category,
                    confession_id=excluded.confession_id,
                    title=excluded.title,
                    content=excluded.content
            """, (
                msg["id"], channel, msg.get("date"), msg.get("text"),
                msg.get("views", 0), msg.get("forwards", 0), msg.get("reactions_count", 0),
                msg.get("reply_count", 0), msg.get("is_reply", False), msg.get("reply_to_msg_id"),
                msg.get("word_count", 0), msg.get("char_count", 0), now,
                msg.get("category"), msg.get("confession_id"), msg.get("title"), msg.get("content"),
            ))
            inserted += cursor.rowcount
        conn.commit()
        conn.close()
        log.debug("Saved %d/%d messages to database.", inserted, len(messages))
        return inserted
    except sqlite3.Error as e:
        raise RuntimeError(f"Database write failed: {e}") from e


def get_messages(since_date: str = None, until_date: str = None) -> list[dict]:
    try:
        conn = _connect()
        query = "SELECT * FROM messages WHERE 1=1"
        params = []
        if since_date:
            query += " AND date >= ?"
            params.append(since_date)
        if until_date:
            query += " AND date <= ?"
            params.append(until_date + "T23:59:59")
        query += " ORDER BY date ASC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        log.debug("Loaded %d messages from database.", len(rows))
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        raise RuntimeError(f"Database read failed: {e}") from e


def get_latest_id() -> int:
    try:
        conn = _connect()
        row = conn.execute("SELECT MAX(id) FROM messages").fetchone()
        conn.close()
        latest = row[0] or 0
        log.debug("Latest message ID in DB: %d", latest)
        return latest
    except sqlite3.Error as e:
        raise RuntimeError(f"Database read failed: {e}") from e


def save_replies(replies: list[dict]) -> int:
    """Save replies from the linked discussion group. Idempotent on reply_msg_id."""
    if not replies:
        return 0
    try:
        conn = _connect()
        now = datetime.utcnow().isoformat()
        inserted = 0
        for r in replies:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO replies
                    (post_id, linked_parent_id, reply_msg_id, date, text,
                     author, reactions_up, reactions_down, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get("post_id"),
                r.get("linked_parent_id"),
                r.get("reply_msg_id"),
                r.get("date"),
                r.get("text"),
                r.get("author"),
                r.get("reactions_up", 0),
                r.get("reactions_down", 0),
                now,
            ))
            if cursor.rowcount:
                inserted += 1
        conn.commit()
        conn.close()
        log.debug("Saved %d/%d replies to database.", inserted, len(replies))
        return inserted
    except sqlite3.Error as e:
        raise RuntimeError(f"Database write failed (replies): {e}") from e


def get_replies_for_post(post_id: int) -> list[dict]:
    """Get all replies for a specific channel post."""
    try:
        conn = _connect()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM replies WHERE post_id = ? ORDER BY date ASC",
            (post_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        raise RuntimeError(f"Database read failed: {e}") from e


def get_latest_reply_msg_id() -> int:
    """Get the highest reply_msg_id we've already stored."""
    try:
        conn = _connect()
        row = conn.execute("SELECT MAX(reply_msg_id) FROM replies").fetchone()
        conn.close()
        return row[0] or 0
    except sqlite3.Error as e:
        raise RuntimeError(f"Database read failed: {e}") from e


def get_earliest_reply_msg_id() -> int:
    """Get the lowest reply_msg_id we've stored (oldest processed)."""
    try:
        conn = _connect()
        row = conn.execute("SELECT MIN(reply_msg_id) FROM replies").fetchone()
        conn.close()
        return row[0] or 0
    except sqlite3.Error as e:
        raise RuntimeError(f"Database read failed: {e}") from e


def get_all_replies_count() -> int:
    """Total stored replies."""
    try:
        conn = _connect()
        row = conn.execute("SELECT COUNT(*) FROM replies").fetchone()
        conn.close()
        return row[0] or 0
    except sqlite3.Error as e:
        raise RuntimeError(f"Database read failed: {e}") from e
