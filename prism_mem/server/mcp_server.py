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
    from prism_mem.linking.linker import search_similar
    from prism_mem.storage.db import embed, open_db

    try:
        conn = open_db(_project_path)
    except Exception as e:
        return f"Could not open knowledge graph: {e}"

    query_emb = embed(question)
    results = search_similar(conn, query_emb, top_k=5)

    if not results:
        conn.close()
        return "No matching triples found. Knowledge graph may be empty — run `prism crystallize` first."

    lines = []
    for triple_id, cosine_sim in results:
        t = conn.execute(
            "SELECT subject, predicate, object FROM triples WHERE id = ?",
            (triple_id,),
        ).fetchone()
        if t:
            lines.append(f"[{cosine_sim:.2f}] ({t['subject']}) [{t['predicate']}] ({t['object']})")

    conn.close()
    return "\n".join(lines) if lines else "No matching triples found."


@mcp.tool()
def crystallize(session_id: str = "") -> str:
    """Trigger the full crystallize pipeline for the project in the background.

    Extraction + constitution generation take several minutes (kg-gen API calls).
    Returns immediately; CLAUDE.md will be updated when done.
    """
    from prism_mem.config import is_config_complete
    if not is_config_complete():
        return "Cannot crystallize: prism is not configured. Run `prism config set provider/model/api-key` first."
    cmd = ["prism", "crystallize", "--project", _project_path]
    if session_id:
        cmd += ["--session", session_id]
    subprocess.Popen(cmd, start_new_session=True)
    return f"Crystallize started for {_project_path}. CLAUDE.md will be updated in a few minutes."


def start_mcp_server(project_path: str = ".") -> None:
    global _project_path
    _project_path = str(Path(project_path).resolve())
    mcp.run()
