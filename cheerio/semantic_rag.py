"""Optional local embedding layer for the existing SQLite FTS5 document index."""
from __future__ import annotations

import json
from contextlib import closing
import math
import os
from pathlib import Path
import sqlite3
from urllib.request import Request, urlopen

from .rag import index_path

MAX_DIM = 4096


def embedding_model():
    return os.environ.get("CHEERIO_EMBED_MODEL", "embeddinggemma")


def embed(text, model=None):
    """Ollama's local /api/embed only. Never forward indexed documents to a remote URL."""
    model = model or embedding_model()
    if not model or len(model) > 100:
        raise ValueError("Invalid local embedding model")
    payload = json.dumps({"model": model, "input": text, "truncate": True}).encode()
    req = Request("http://127.0.0.1:11434/api/embed", data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=45) as response:
        result = json.loads(response.read(2_000_000))
    vector = result["embeddings"][0]
    if not isinstance(vector, list) or not 1 <= len(vector) <= MAX_DIM or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
        raise ValueError("Invalid embedding vector")
    return vector


def build_vectors(db=None, embedder=embed, model=None):
    """Build complete snapshot before replacing existing vectors; opt-in CLI operation."""
    db = Path(db) if db is not None else index_path()
    if not db.exists():
        raise ValueError("Index a document folder first")
    model = model or embedding_model()
    with closing(sqlite3.connect(db)) as conn, conn:
        chunks = conn.execute("SELECT rowid,content FROM chunks ORDER BY rowid LIMIT 3001").fetchall()
        if len(chunks) > 3000:
            raise ValueError("Semantic index limited to 3000 chunks; keyword search remains available")
        vectors = [(rowid, json.dumps(embedder(content, model))) for rowid, content in chunks]
        dimensions = {len(json.loads(v)) for _, v in vectors}
        if any(not isinstance(x, (int, float)) or not math.isfinite(x) for _, v in vectors for x in json.loads(v)):
            raise ValueError("Invalid embedding vector")
        if len(dimensions) > 1:
            raise ValueError("Embedding dimensions changed during indexing")
        conn.execute("CREATE TABLE IF NOT EXISTS rag_vectors(chunk_id INTEGER PRIMARY KEY, model TEXT NOT NULL, vector TEXT NOT NULL)")
        conn.execute("DELETE FROM rag_vectors")
        conn.executemany("INSERT INTO rag_vectors VALUES (?,?,?)", [(rid, model, vec) for rid, vec in vectors])
    return len(vectors)


def _cosine(a, b):
    if len(a) != len(b):
        return 0.0
    norm = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / norm if norm else 0.0


def semantic_search(query, db=None, limit=5, embedder=embed, model=None):
    db = Path(db) if db is not None else index_path()
    if not db.exists():
        return []
    model = model or embedding_model()
    with closing(sqlite3.connect(db)) as conn, conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='rag_vectors'").fetchone():
            return []
        rows = conn.execute("SELECT c.path,c.position,c.content,v.vector FROM rag_vectors v JOIN chunks c ON c.rowid=v.chunk_id WHERE v.model=?", (model,)).fetchall()
    if not rows:
        return []
    query_vector = embedder(query, model)
    ranked = sorted(((_cosine(query_vector, json.loads(vector)), path, position, content) for path, position, content, vector in rows), reverse=True)
    return [{"path": path, "position": position, "excerpt": content[:900], "score": round(score, 4)} for score, path, position, content in ranked[:max(1, min(int(limit), 8))] if score > 0]


def hybrid_search(query, db=None, limit=5, embedder=embed, model=None):
    from .rag import search
    keywords = search(query, db=db, limit=8)
    semantics = semantic_search(query, db=db, limit=8, embedder=embedder, model=model)
    ranked = {}
    # Reciprocal rank fusion: no incomparable FTS/cosine score arithmetic.
    for results in (keywords, semantics):
        for rank, item in enumerate(results):
            key = (item["path"], item["position"])
            score, _ = ranked.get(key, (0, item))
            ranked[key] = (score + 1/(20+rank), item)
    return [item for _, item in sorted(ranked.values(), key=lambda pair: pair[0], reverse=True)[:max(1, min(int(limit), 8))]]
