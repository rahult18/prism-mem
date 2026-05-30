from kg_gen import KGGen
from kg_gen.models import Graph

from prism_mem.config import get_api_key, get_model_string

CHUNK_SIZE = 8000

_kg = None


def _get_kg() -> KGGen:
    global _kg
    if _kg is None:
        _kg = KGGen(
            model=get_model_string(),
            api_key=get_api_key(),
            temperature=0.0,
        )
    return _kg


def extract_triples(text: str, context: str = "") -> list[tuple[str, str, str]]:
    """Extract (subject, predicate, object) triples from text using kg-gen.

    Args:
        text: Combined session + git text to extract from.
        context: One-line description of what the text is about (improves quality).

    Returns:
        List of (subject, predicate, object) tuples.
    """
    if not text.strip():
        return []

    kg = _get_kg()
    graph: Graph = kg.generate(
        input_data=text,
        context=context,
        chunk_size=CHUNK_SIZE,
        cluster=True,
    )
    return list(graph.relations)


if __name__ == "__main__":
    import sys
    from prism_mem.ingestion.session_reader import read_latest_session
    from prism_mem.ingestion.git_reader import read_git_diff, read_git_log

    project = sys.argv[1] if len(sys.argv) > 1 else "."

    print("Reading session chunks...", flush=True)
    chunks = read_latest_session(project)
    session_text = "\n\n".join(
        f"[{c['role']}] {c['content']}"
        for c in chunks
        if c["content_type"] in ("text", "summary")
    )

    print("Reading git history...", flush=True)
    git_text = "\n\n".join(filter(None, [
        read_git_log(project),
        read_git_diff(project),
    ]))

    combined = "\n\n---\n\n".join(filter(None, [session_text, git_text]))
    print(f"Input: {len(combined):,} chars across {len(chunks)} chunks\n", flush=True)

    print("Extracting triples (this calls the Anthropic API)...\n", flush=True)
    triples = extract_triples(
        combined,
        context="Claude Code session transcript and git history for a Python project",
    )

    print(f"Extracted {len(triples)} triples:\n")
    for subj, pred, obj in sorted(triples):
        print(f"  ({subj})  --[{pred}]-->  ({obj})")
