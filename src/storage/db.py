import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "messages.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
    conn.commit()
    conn.close()


def save_messages(messages: list[dict], channel: str = "NUSConfessIT"):
    conn = sqlite3.connect(DB_PATH)
    now = datetime.utcnow().isoformat()
    for msg in messages:
        conn.execute("""
            INSERT INTO messages (id, channel, date, text, views, forwards, reactions_count,
                reply_count, is_reply, reply_to_msg_id, word_count, char_count, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id, channel) DO UPDATE SET
                views=excluded.views, forwards=excluded.forwards,
                reactions_count=excluded.reactions_count, reply_count=excluded.reply_count,
                scraped_at=excluded.scraped_at
        """, (
            msg["id"], channel, msg.get("date"), msg.get("text"),
            msg.get("views", 0), msg.get("forwards", 0), msg.get("reactions_count", 0),
            msg.get("reply_count", 0), msg.get("is_reply", False), msg.get("reply_to_msg_id"),
            msg.get("word_count", 0), msg.get("char_count", 0), now
        ))
    conn.commit()
    conn.close()


def get_messages(since_date: str = None, until_date: str = None) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
    return [dict(r) for r in rows]


def get_latest_id() -> int:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT MAX(id) FROM messages").fetchone()
    conn.close()
    return row[0] or 0
