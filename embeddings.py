"""
CLARA-AGI v1.4 - Embeddings helper.
- embed(text): call Ollama POST /api/embeddings with model "nomic-embed-text"
- Cache into SQLite table semantics_embeddings to avoid recompute.
- Returns None when Ollama/model not available.
"""
import json
import os
import sqlite3
import time
import urllib.request
from pathlib import Path

try:
    from memory import DB_DIR
except Exception:
    DB_DIR = Path(__file__).parent / "data"

DB_DIR.mkdir(exist_ok=True)
EMBED_DB_PATH = DB_DIR / "embeddings.db"

OLLAMA_URL = os.environ.get("CLARA_OLLAMA_URL", "http://localhost:11434")
DEFAULT_EMBED_MODEL = "nomic-embed-text"


def _get_conn():
    conn = sqlite3.connect(str(EMBED_DB_PATH), check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            text TEXT PRIMARY KEY,
            model TEXT,
            vector TEXT,
            ts REAL
        )
    """)
    conn.commit()
    return conn


def ollama_embeddings(text, model=DEFAULT_EMBED_MODEL, url=OLLAMA_URL):
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        j = json.loads(resp.read())
    vec = j.get("embedding")
    if not isinstance(vec, list):
        return None
    return vec


def embed(text, model=DEFAULT_EMBED_MODEL):
    text = (text or "").strip()
    if not text:
        return None
    conn = _get_conn()
    row = conn.execute("SELECT vector FROM cache WHERE text=? AND model=?", (text, model)).fetchone()
    if row:
        return json.loads(row["vector"])
    try:
        vec = ollama_embeddings(text, model=model)
    except Exception:
        return None
    if vec is None:
        return None
    try:
        conn.execute("INSERT OR REPLACE INTO cache(text, model, vector, ts) VALUES(?,?,?,?)",
                     (text, model, json.dumps(vec), time.time()))
        conn.commit()
    except Exception:
        pass
    return vec


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
