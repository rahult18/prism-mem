import hashlib
import sqlite3
import struct
from datetime import datetime
from pathlib import Path

import sqlite_vec
from sentence_transformers import SentenceTransformer

from prism_mem.config import PROJECTS_DIR
from prism_mem.storage.models import Edge, Triple

EMBEDDING_DIM = 384
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text: str) -> bytes:
    vec = _get_model().encode(text, normalize_embeddings=True)
    return struct.pack(f"{EMBEDDING_DIM}f", *vec)


def project_hash(project_path: str) -> str:
    return hashlib.sha256(str(Path(project_path).resolve()).encode()).hexdigest()[:16]


def db_path(project_path: str) -> Path:
    return PROJECTS_DIR / project_hash(project_path) / "graph.db"


def open_db(project_path: str) -> sqlite3.Connection:
    path = db_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS triples (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            subject   TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object    TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            session_id TEXT NOT NULL DEFAULT '',
            timestamp  TEXT NOT NULL,
            stale      INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS edges (
            from_id   INTEGER NOT NULL,
            to_id     INTEGER NOT NULL,
            edge_type TEXT NOT NULL,
            weight    REAL NOT NULL,
            PRIMARY KEY (from_id, to_id, edge_type)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS vec_triples
            USING vec0(embedding float[{EMBEDDING_DIM}]);
    """)
    conn.commit()


def store_triple(conn: sqlite3.Connection, triple: Triple) -> int:
    ts = triple.timestamp.isoformat() if isinstance(triple.timestamp, datetime) else triple.timestamp
    cur = conn.execute(
        """
        INSERT INTO triples (subject, predicate, object, confidence, session_id, timestamp, stale)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (triple.subject, triple.predicate, triple.object,
         triple.confidence, triple.session_id, ts, int(triple.stale)),
    )
    triple_id = cur.lastrowid
    embedding = embed(f"{triple.subject} {triple.predicate} {triple.object}")
    conn.execute(
        "INSERT INTO vec_triples(rowid, embedding) VALUES (?, ?)",
        (triple_id, embedding),
    )
    conn.commit()
    return triple_id


def get_all_triples(conn: sqlite3.Connection) -> list[Triple]:
    rows = conn.execute("SELECT * FROM triples ORDER BY id").fetchall()
    return [_row_to_triple(r) for r in rows]


def get_triple_by_id(conn: sqlite3.Connection, triple_id: int) -> Triple | None:
    row = conn.execute("SELECT * FROM triples WHERE id = ?", (triple_id,)).fetchone()
    return _row_to_triple(row) if row else None


def mark_stale(conn: sqlite3.Connection, triple_id: int) -> None:
    conn.execute("UPDATE triples SET stale = 1 WHERE id = ?", (triple_id,))
    conn.commit()


def _row_to_triple(row: sqlite3.Row) -> Triple:
    return Triple(
        id=row["id"],
        subject=row["subject"],
        predicate=row["predicate"],
        object=row["object"],
        confidence=row["confidence"],
        session_id=row["session_id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        stale=bool(row["stale"]),
    )


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "."

    print(f"DB path: {db_path(project)}")
    conn = open_db(project)

    # Store a few test triples
    test_triples = [
        Triple(subject="prism-mem", predicate="uses", object="sqlite-vec", session_id="test"),
        Triple(subject="prism-mem", predicate="uses", object="kg-gen", session_id="test"),
        Triple(subject="session_reader", predicate="parses", object="JSONL", session_id="test"),
    ]
    for t in test_triples:
        tid = store_triple(conn, t)
        print(f"Stored triple id={tid}: ({t.subject}) --[{t.predicate}]--> ({t.object})")

    all_t = get_all_triples(conn)
    print(f"\nTotal triples in DB: {len(all_t)}")

    # Verify embeddings
    count = conn.execute("SELECT count(*) FROM vec_triples").fetchone()[0]
    print(f"Embeddings stored: {count}")
    conn.close()
