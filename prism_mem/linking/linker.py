import sqlite3

import numpy as np

from prism_mem.config import SIMILARITY_THRESHOLD
from prism_mem.storage.db import mark_stale, store_triple, vec_from_bytes
from prism_mem.storage.models import Edge, Triple


def search_similar(
    conn: sqlite3.Connection,
    query_bytes: bytes,
    top_k: int = 5,
    exclude_id: int | None = None,
) -> list[tuple[int, float]]:
    """Return [(triple_id, cosine_similarity), ...] for non-stale triples near query_bytes."""
    if exclude_id is not None:
        rows = conn.execute(
            """
            SELECT e.triple_id, e.embedding FROM embeddings e
            JOIN triples t ON t.id = e.triple_id
            WHERE t.stale = 0 AND e.triple_id != ?
            """,
            (exclude_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT e.triple_id, e.embedding FROM embeddings e
            JOIN triples t ON t.id = e.triple_id
            WHERE t.stale = 0
            """,
        ).fetchall()

    if not rows:
        return []

    query_vec = vec_from_bytes(query_bytes)
    ids = [r["triple_id"] for r in rows]
    matrix = np.array([vec_from_bytes(r["embedding"]) for r in rows], dtype=np.float32)
    sims = matrix @ query_vec

    top_indices = np.argsort(sims)[::-1][:top_k]
    results = []
    for i in top_indices:
        if float(sims[i]) >= SIMILARITY_THRESHOLD:
            results.append((ids[i], float(sims[i])))
    return results


def find_similar(
    conn: sqlite3.Connection,
    triple_id: int,
    top_k: int = 5,
) -> list[tuple[int, float]]:
    """Return [(other_id, cosine_similarity), ...] for non-stale triples near triple_id."""
    row = conn.execute(
        "SELECT embedding FROM embeddings WHERE triple_id = ?", (triple_id,)
    ).fetchone()
    if not row:
        return []
    return search_similar(conn, row["embedding"], top_k=top_k, exclude_id=triple_id)


def create_edge(
    conn: sqlite3.Connection,
    from_id: int,
    to_id: int,
    edge_type: str,
    weight: float,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO edges (from_id, to_id, edge_type, weight)
        VALUES (?, ?, ?, ?)
        """,
        (from_id, to_id, edge_type, weight),
    )
    conn.commit()


def check_and_mark_stale(conn: sqlite3.Connection, triple: Triple) -> list[int]:
    """Mark existing triples with same subject+predicate but different object as stale.

    Returns list of IDs that were marked stale.
    """
    rows = conn.execute(
        """
        SELECT id FROM triples
        WHERE subject = ? AND predicate = ? AND object != ? AND stale = 0
        """,
        (triple.subject, triple.predicate, triple.object),
    ).fetchall()
    stale_ids = [r["id"] for r in rows]
    for sid in stale_ids:
        mark_stale(conn, sid)
    return stale_ids


def link_triple(conn: sqlite3.Connection, triple_id: int) -> list[Edge]:
    """Find similar triples and create edges. Returns created edges."""
    similar = find_similar(conn, triple_id)
    edges = []
    for other_id, similarity in similar:
        create_edge(conn, triple_id, other_id, "similar", round(similarity, 4))
        edges.append(Edge(from_id=triple_id, to_id=other_id, edge_type="similar", weight=round(similarity, 4)))
    return edges


def ingest_triple(conn: sqlite3.Connection, triple: Triple) -> tuple[int, list[int], list[Edge]]:
    """Store a triple, link to similar triples, then detect staleness.

    Order matters: link first (while old triples are still non-stale so they
    appear in similarity search), then mark old conflicting triples stale.

    Returns (triple_id, stale_ids, edges_created).
    """
    triple_id = store_triple(conn, triple)
    edges = link_triple(conn, triple_id)
    stale_ids = check_and_mark_stale(conn, triple)
    return triple_id, stale_ids, edges


if __name__ == "__main__":
    import sys
    from prism_mem.storage.db import get_all_triples, open_db
    from prism_mem.storage.models import Triple

    project = sys.argv[1] if len(sys.argv) > 1 else "."
    conn = open_db(project)

    print("=== Storing triples (non-conflicting similar pairs) ===")
    batch = [
        Triple(subject="session_reader", predicate="reads", object="JSONL session files", session_id="t1"),
        Triple(subject="session_reader", predicate="reads", object="JSONL transcript files", session_id="t1"),
        Triple(subject="kg-gen", predicate="extracts", object="knowledge graph triples", session_id="t1"),
        Triple(subject="kg-gen", predicate="generates", object="knowledge graph triples", session_id="t1"),
        Triple(subject="prism-mem", predicate="uses", object="sqlite-vec", session_id="t1"),
        Triple(subject="prism-mem", predicate="stores", object="triples in SQLite", session_id="t1"),
    ]
    for t in batch:
        tid, stale, edges = ingest_triple(conn, t)
        print(f"  id={tid}: ({t.subject}) --[{t.predicate}]--> ({t.object})  edges={len(edges)}  stale_marked={stale}")

    print("\n=== All edges ===")
    rows = conn.execute("SELECT from_id, to_id, edge_type, weight FROM edges ORDER BY weight DESC").fetchall()
    if rows:
        for r in rows:
            t_from = conn.execute("SELECT subject, predicate, object FROM triples WHERE id=?", (r["from_id"],)).fetchone()
            t_to   = conn.execute("SELECT subject, predicate, object FROM triples WHERE id=?", (r["to_id"],)).fetchone()
            print(f"  [{r['weight']:.3f}] ({t_from['subject']} {t_from['predicate']} {t_from['object']}) <-> ({t_to['subject']} {t_to['predicate']} {t_to['object']})")
    else:
        print("  (none)")

    print("\n=== Staleness test ===")
    # Store a fact, then contradict it
    tid1, _, _ = ingest_triple(conn, Triple(subject="prism-mem", predicate="embedding-model", object="text-embedding-3-small", session_id="t2"))
    print(f"  Stored id={tid1}: prism-mem embedding-model text-embedding-3-small")
    tid2, stale_ids, _ = ingest_triple(conn, Triple(subject="prism-mem", predicate="embedding-model", object="all-MiniLM-L6-v2", session_id="t3"))
    print(f"  Stored id={tid2}: prism-mem embedding-model all-MiniLM-L6-v2")
    print(f"  Marked stale: {stale_ids}  (expected: [{tid1}])")
    stale_rows = conn.execute("SELECT id, subject, predicate, object FROM triples WHERE stale=1").fetchall()
    for r in stale_rows:
        print(f"  Stale id={r['id']}: ({r['subject']}) --[{r['predicate']}]--> ({r['object']})")

    conn.close()
