#!/usr/bin/env python3
"""One-time bulk load of precomputed embeddings into data/vectors.db.

Reads data/embeddings_v5.npy + data/embedding_ids_v5.npy (memory-mapped,
streamed in batches — low RAM) and inserts them into a sqlite-vec vec0
table with cosine distance. Idempotent: already-present ids are skipped.

Usage: venv/bin/python3 build_vector_db.py
"""
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.search.semantic import EMBED_DIMS, connect_vec_db, ensure_vec_table

REPO = Path(__file__).resolve().parent
EMB_PATH = REPO / "data" / "embeddings_v5.npy"
IDS_PATH = REPO / "data" / "embedding_ids_v5.npy"

BATCH = 2048


def main():
    emb = np.load(EMB_PATH, mmap_mode="r")
    ids = np.load(IDS_PATH, mmap_mode="r")
    assert emb.shape[0] == ids.shape[0], "embeddings/ids length mismatch"
    assert emb.shape[1] == EMBED_DIMS, f"expected {EMBED_DIMS} dims, got {emb.shape[1]}"

    conn = connect_vec_db()
    ensure_vec_table(conn)
    existing = {r[0] for r in conn.execute("SELECT id FROM vec_posts")}
    print(f"corpus: {emb.shape[0]} vectors | already loaded: {len(existing)}")

    inserted = 0
    for start in range(0, emb.shape[0], BATCH):
        batch_ids = ids[start:start + BATCH]
        batch_emb = np.ascontiguousarray(emb[start:start + BATCH], dtype=np.float32)
        rows = [
            (int(pid), struct.pack(f"{EMBED_DIMS}f", *vec))
            for pid, vec in zip(batch_ids, batch_emb)
            if int(pid) not in existing
        ]
        if rows:
            conn.executemany(
                "INSERT INTO vec_posts(id, embedding) VALUES (?, ?)", rows
            )
            conn.commit()
            inserted += len(rows)
        print(f"  {min(start + BATCH, emb.shape[0])}/{emb.shape[0]} (+{inserted})",
              flush=True)

    total = conn.execute("SELECT COUNT(*) FROM vec_posts").fetchone()[0]
    conn.close()
    print(f"done: inserted {inserted}, table now holds {total} vectors")


if __name__ == "__main__":
    main()
