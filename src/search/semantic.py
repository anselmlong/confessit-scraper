"""Semantic search over confession embeddings via sqlite-vec.

Vectors live in a separate SQLite database (data/vectors.db) holding a
vec0 virtual table with cosine distance. KNN queries scan on disk in
native code — nothing holds the full 65k x 512 float32 matrix in
application memory.

Corpus embeddings: openai/text-embedding-3-small, 512 dims (same model
and dims used by the ml pipeline that produced data/embeddings_v5.npy).
Query embeddings MUST use the same model/dims.
"""
import json
import os
import re
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
VEC_DB_PATH = REPO_ROOT / "data" / "vectors.db"

EMBED_MODEL = "openai/text-embedding-3-small"
EMBED_DIMS = 512

# ── API key (same lookup order as ml/ml_embeddings.py) ─────────────────────

_ENV_PATHS = [
    Path.home() / ".hermes" / ".env",
    REPO_ROOT / ".env",
]
_creds = None  # (api_key, provider) — provider in {"openrouter", "openai"}


def _read_env_var(var):
    if os.environ.get(var):
        return os.environ[var]
    for env_path in _ENV_PATHS:
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip().removeprefix("export ").strip()
            if line.startswith(f"{var}=") and line.split("=", 1)[1]:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _load_creds():
    """Prefer an OpenRouter key; fall back to a direct OpenAI key."""
    global _creds
    if _creds:
        return _creds
    key = _read_env_var("OPENROUTER_API_KEY")
    if key:
        _creds = (key, "openrouter")
        return _creds
    key = _read_env_var("OPENAI_API_KEY")
    if key:
        _creds = (key, "openai")
        return _creds
    return (None, None)


# ── Confession text cleaning (mirrors ml/ml_embeddings.py) ─────────────────

_TEMPLATE_MARKERS = [
    "Click here", "NUSConfessIT_bot",
    "👇 Comment **below** anonymously", "😆 Send an **anonymous message**",
    "Send an **anonymous message**", "PM THIS", "PM Confessor",
    "post a confession", "post **YOUR OWN** confession",
    "post your own anonymous",
]


def _is_template_line(l):
    s = l.strip()
    return bool(s) and any(m in s for m in _TEMPLATE_MARKERS)


def _clean_body(t):
    if not t:
        return None
    ls = t.strip().split("\n")
    for i, l in enumerate(ls):
        if _is_template_line(l):
            if i == 0:
                return None
            return "\n".join(ls[:i]).strip() or None
    return t.strip()


def extract_confession_text(raw):
    """Extract embeddable confession body from a raw message."""
    if not raw:
        return None
    m = re.search(r"---\s*\n(.*?)\n---", raw, re.DOTALL)
    text = m.group(1).strip() if m else _clean_body(raw)
    if not text or len(text) < 10:
        return None
    if sum(c.isalpha() for c in text) / max(len(text), 1) < 0.2:
        return None
    return text


# ── Embedding API ───────────────────────────────────────────────────────────

def embed_texts(texts, timeout=30):
    """Embed texts via OpenRouter (or OpenAI directly). Returns float lists."""
    api_key, provider = _load_creds()
    if not api_key:
        raise RuntimeError(
            "No OPENROUTER_API_KEY/OPENAI_API_KEY found in env, "
            "~/.hermes/.env, or project .env"
        )
    if provider == "openrouter":
        url = "https://openrouter.ai/api/v1/embeddings"
        model = EMBED_MODEL
    else:
        url = "https://api.openai.com/v1/embeddings"
        model = EMBED_MODEL.removeprefix("openai/")
    payload = json.dumps({
        "model": model,
        "input": texts,
        "dimensions": EMBED_DIMS,
    }).encode()
    req = Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    return [d["embedding"] for d in result["data"]]


# ── Vector DB ───────────────────────────────────────────────────────────────

def connect_vec_db():
    """Open data/vectors.db with the sqlite-vec extension loaded."""
    import sqlite_vec

    conn = sqlite3.connect(VEC_DB_PATH)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def ensure_vec_table(conn):
    conn.execute(
        f"""CREATE VIRTUAL TABLE IF NOT EXISTS vec_posts USING vec0(
            id INTEGER PRIMARY KEY,
            embedding FLOAT[{EMBED_DIMS}] distance_metric=cosine
        )"""
    )


def semantic_search_ids(query, k=25):
    """Return [(post_id, similarity)] for the k nearest posts.

    similarity = 1 - cosine_distance, in [0, 1]-ish for normalized text.
    """
    if not VEC_DB_PATH.exists():
        raise RuntimeError(f"{VEC_DB_PATH} missing — run build_vector_db.py")
    import struct

    vec = embed_texts([query])[0]
    blob = struct.pack(f"{EMBED_DIMS}f", *vec)
    conn = connect_vec_db()
    try:
        rows = conn.execute(
            "SELECT id, distance FROM vec_posts WHERE embedding MATCH ? AND k = ?",
            (blob, k),
        ).fetchall()
    finally:
        conn.close()
    return [(int(r[0]), 1.0 - float(r[1])) for r in rows]
