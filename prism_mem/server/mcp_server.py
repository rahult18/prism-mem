import subprocess
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("prism")
_project_path: str = "."


@mcp.tool()
def get_context() -> str:
    """Return the current CLAUDE.md content for the project."""
    p = Path(_project_path) / "CLAUDE.md"
    if not p.exists():
        return "No CLAUDE.md found. Run `prism crystallize --project <path>` first."
    return p.read_text(encoding="utf-8")


@mcp.tool()
def query_knowledge(question: str) -> str:
    """Semantic search over the project knowledge graph. Returns top-5 matching triples."""
    from prism_mem.storage.db import embed, open_db

    try:
        conn = open_db(_project_path)
    except Exception as e:
        return f"Could not open knowledge graph: {e}"

    query_emb = embed(question)
    try:
        rows = conn.execute(
            """
            SELECT vt.rowid, vt.distance
            FROM vec_triples vt
            JOIN triples t ON t.id = vt.rowid
            WHERE vt.embedding MATCH ?
              AND vt.k = 5
              AND t.stale = 0
            ORDER BY vt.distance
            """,
            (query_emb,),
        ).fetchall()
    except Exception:
        conn.close()
        return "Knowledge graph is empty. Run `prism crystallize` first."

    if not rows:
        conn.close()
        return "No matching triples found."

    lines = []
    for row in rows:
        t = conn.execute(
            "SELECT subject, predicate, object FROM triples WHERE id = ?",
            (row["rowid"],),
        ).fetchone()
        cosine_sim = 1.0 - (row["distance"] ** 2) / 2.0
        lines.append(f"[{cosine_sim:.2f}] ({t['subject']}) [{t['predicate']}] ({t['object']})")

    conn.close()
    return "\n".join(lines)


@mcp.tool()
def crystallize(session_id: str = "") -> str:
    """Trigger the full crystallize pipeline for the project in the background.

    Extraction + constitution generation take several minutes (kg-gen API calls).
    Returns immediately; CLAUDE.md will be updated when done.
    """
    cmd = ["prism", "crystallize", "--project", _project_path]
    if session_id:
        cmd += ["--session", session_id]
    subprocess.Popen(cmd, start_new_session=True)
    return f"Crystallize started for {_project_path}. CLAUDE.md will be updated in a few minutes."


def start_mcp_server(project_path: str = ".") -> None:
    global _project_path
    _project_path = str(Path(project_path).resolve())
    mcp.run()
