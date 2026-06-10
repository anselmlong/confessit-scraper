#!/usr/bin/env python3
"""Embed posts that are missing from data/vectors.db.

Picked up automatically by weekly_refresh.sh. Finds non-reply posts in
data/messages.db whose ids are absent from the vec_posts table, embeds
their cleaned confession text via OpenRouter (same model/dims as the
corpus), and inserts the vectors. Posts whose text fails the cleaning
filters (template-only, too short, non-text) are skipped permanently.

Usage: venv/bin/python3 refresh_embeddings.py [--dry-run]
"""
import argparse
import sqlite3
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.search.semantic import (
    EMBED_DIMS,
    connect_vec_db,
    ensure_vec_table,
    embed_texts,
    extract_confession_text,
)

REPO = Path(__file__).resolve().parent
DB_PATH = REPO / "data" / "messages.db"

BATCH = 128


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be embedded, change nothing")
    args = parser.parse_args()

    vec_conn = connect_vec_db()
    ensure_vec_table(vec_conn)
    existing = {r[0] for r in vec_conn.execute("SELECT id FROM vec_posts")}

    msg_conn = sqlite3.connect(DB_PATH)
    rows = msg_conn.execute(
        "SELECT id, COALESCE(NULLIF(content,''),NULLIF(text,'')) "
        "FROM messages WHERE is_reply=0"
    ).fetchall()
    msg_conn.close()

    todo = []
    skipped = 0
    for pid, raw in rows:
        if pid in existing:
            continue
        text = extract_confession_text(raw)
        if text:
            todo.append((pid, text))
        else:
            skipped += 1

    print(f"posts: {len(rows)} | embedded: {len(existing)} | "
          f"to embed: {len(todo)} | unembeddable: {skipped}")
    if args.dry_run or not todo:
        vec_conn.close()
        return

    inserted = 0
    for start in range(0, len(todo), BATCH):
        batch = todo[start:start + BATCH]
        vectors = embed_texts([t for _, t in batch], timeout=60)
        vec_conn.executemany(
            "INSERT INTO vec_posts(id, embedding) VALUES (?, ?)",
            [
                (pid, struct.pack(f"{EMBED_DIMS}f", *vec))
                for (pid, _), vec in zip(batch, vectors)
            ],
        )
        vec_conn.commit()
        inserted += len(batch)
        print(f"  {inserted}/{len(todo)}", flush=True)
        if start + BATCH < len(todo):
            time.sleep(0.1)

    vec_conn.close()
    print(f"done: embedded {inserted} new posts")


if __name__ == "__main__":
    main()
