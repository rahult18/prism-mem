from datetime import datetime, timezone
from pathlib import Path

import anthropic

from prism_mem.config import ANTHROPIC_API_KEY, HAIKU_MODEL, TOP_TRIPLES_FOR_CONSTITUTION
from prism_mem.storage.db import get_all_triples, open_db
from prism_mem.storage.models import Triple

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _score(triple: Triple, now: datetime) -> float:
    age_seconds = max((now - triple.timestamp.replace(tzinfo=None)).total_seconds(), 1)
    recency = 1.0 / (1.0 + age_seconds / 86400)  # decays over days
    return recency + triple.confidence


def select_top_triples(triples: list[Triple], n: int = TOP_TRIPLES_FOR_CONSTITUTION) -> list[Triple]:
    now = datetime.utcnow()
    active = [t for t in triples if not t.stale]
    return sorted(active, key=lambda t: _score(t, now), reverse=True)[:n]


def _format_triples(triples: list[Triple]) -> str:
    lines = []
    for t in triples:
        lines.append(f"- ({t.subject}) [{t.predicate}] ({t.object})")
    return "\n".join(lines)


def _call_haiku(prompt: str) -> str:
    msg = _get_client().messages.create(
        model=HAIKU_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def generate_claude_md(triples: list[Triple]) -> str:
    facts = _format_triples(triples)
    prompt = f"""You are generating a CLAUDE.md file for an AI coding agent.

Below are structured knowledge graph facts extracted from real coding sessions and git history for this project. Each fact is: (subject) [predicate] (object).

FACTS:
{facts}

Write a CLAUDE.md that:
1. Starts with a one-paragraph description of what this project is and does
2. Has a "## Tech Stack" section listing key technologies and why they were chosen
3. Has a "## Architecture" section describing key components and how they connect
4. Has a "## Key Decisions" section listing important non-obvious decisions and their rationale
5. Has a "## Conventions" section with any patterns, naming, or workflow conventions evident from the facts

Be concise and specific. Only include facts that are directly supported by the knowledge graph. Do not invent information. Write in present tense."""
    return _call_haiku(prompt)


def generate_cursorrules(triples: list[Triple]) -> str:
    facts = _format_triples(triples)
    prompt = f"""You are generating a .cursorrules file for a Cursor AI coding assistant.

Below are structured knowledge graph facts extracted from real coding sessions for this project.

FACTS:
{facts}

Write a .cursorrules file that:
- Uses short bullet points (one per line, starting with -)
- Covers: project purpose, key tech stack items, important architectural rules, and conventions to follow
- Is under 40 lines total
- Is direct and imperative ("Use X", "Never Y", "Always Z")

Only include facts directly supported by the knowledge graph."""
    return _call_haiku(prompt)


def generate_agents_md(triples: list[Triple]) -> str:
    facts = _format_triples(triples)
    prompt = f"""You are generating an AGENTS.md file for an OpenAI Codex-style coding agent.

Below are structured knowledge graph facts extracted from real coding sessions for this project.

FACTS:
{facts}

Write an AGENTS.md that:
1. Starts with a one-sentence description of the project
2. Has a "## Repository Layout" section describing the key files and directories
3. Has a "## Build & Run" section with how to install and run the project
4. Has a "## Rules" section with 5-10 important rules the agent must follow

Only include facts directly supported by the knowledge graph. Be concise."""
    return _call_haiku(prompt)


def write_constitution(project_path: str, api_key: str | None = None) -> dict[str, Path]:
    """Generate and write CLAUDE.md, .cursorrules, and AGENTS.md to the project root.

    Returns dict of {filename: path} for files written.
    """
    if api_key:
        global _client
        _client = anthropic.Anthropic(api_key=api_key)

    conn = open_db(project_path)
    all_triples = get_all_triples(conn)
    conn.close()

    top = select_top_triples(all_triples)
    if not top:
        raise ValueError("No non-stale triples in DB — run crystallize first.")

    root = Path(project_path).resolve()
    written = {}

    claude_md = generate_claude_md(top)
    p = root / "CLAUDE.md"
    p.write_text(claude_md, encoding="utf-8")
    written["CLAUDE.md"] = p

    cursorrules = generate_cursorrules(top)
    p = root / ".cursorrules"
    p.write_text(cursorrules, encoding="utf-8")
    written[".cursorrules"] = p

    agents_md = generate_agents_md(top)
    p = root / "AGENTS.md"
    p.write_text(agents_md, encoding="utf-8")
    written["AGENTS.md"] = p

    return written


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    api_key = sys.argv[2] if len(sys.argv) > 2 else None

    print("Loading triples from DB...")
    conn = open_db(project)
    triples = get_all_triples(conn)
    conn.close()
    active = [t for t in triples if not t.stale]
    print(f"  {len(triples)} total, {len(active)} non-stale")

    top = select_top_triples(triples)
    print(f"  Top {len(top)} selected for constitution\n")

    print("Generating constitution files (calling Haiku)...")
    written = write_constitution(project, api_key=api_key)
    for name, path in written.items():
        print(f"  Wrote {name} ({path.stat().st_size} bytes)")

    print("\n--- CLAUDE.md preview (first 40 lines) ---")
    lines = (written["CLAUDE.md"]).read_text().splitlines()
    print("\n".join(lines[:40]))
