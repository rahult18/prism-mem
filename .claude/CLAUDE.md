# Prism — CLAUDE.md

## What This Project Is

Prism is a post-session knowledge crystallizer for AI coding agents. It reads Claude Code session transcripts (JSONL files) and git history, extracts structured semantic knowledge as triples, links them into a graph, and auto-regenerates the context files that every agent reads at session start (CLAUDE.md, .cursorrules, AGENTS.md).

**The one-liner:** Every coding session leaves behind artifacts. Prism reads them and turns them into structured, linked, reusable knowledge — automatically, with no manual input from the user.

**Package name:** `prism-mem` on PyPI. The CLI command is `prism`.

---

## Architecture

### Data Flow

```
[User ends a coding session / makes a git commit]
        ↓
[git post-commit hook calls: prism crystallize --project .]
        ↓
[1] INGEST
    - Read ~/.claude/projects/<encoded-path>/<session-uuid>.jsonl
    - Read: git diff HEAD~1 HEAD  +  git log --oneline -20
        ↓
[2] EXTRACT
    - Feed text chunks to kg-gen
    - kg-gen returns NetworkX graph of (subject, predicate, object) triples
        ↓
[3] STORE + LINK
    - Embed each triple via Anthropic embeddings API
    - Store in SQLite (sqlite-vec) at ~/.prism/projects/<hash>/graph.db
    - For each new triple: query sqlite-vec for nearest existing triples
    - Create edges where similarity > threshold
    - Detect staleness: same subject+predicate, different object → flag old triple
        ↓
[4] GENERATE
    - Score all triples (recency + confidence + retrieval frequency)
    - Take top-N triples → Claude Haiku → write CLAUDE.md
    - Write same knowledge to .cursorrules and AGENTS.md formats
        ↓
[graph.db updated] + [constitution files written to project root]
```

### Storage Layout

```
~/.prism/
└── projects/
    └── <project-hash>/
        └── graph.db         ← SQLite + sqlite-vec, one per project
```

Two tables:
- `triples`: id, subject, predicate, object, confidence, embedding (blob), session_id, timestamp, stale (bool)
- `edges`: from_id, to_id, edge_type, weight

### MCP Server — 3 tools only, no more

| Tool | What it does |
|---|---|
| `get_context()` | Returns current CLAUDE.md content — injected at session start |
| `query_knowledge(question)` | Semantic search over the triple graph |
| `crystallize(session_id)` | Manually trigger extraction for a session |

---

## Project Structure

```
prism-mem/
├── CLAUDE.md                  ← You are here
├── plan.md                    ← Build phases and completion criteria
├── pyproject.toml             ← Package config, deps, entry point
├── requirements.txt           ← Dev dependencies (for venv)
├── prism_mem/
│   ├── __init__.py
│   ├── cli.py                 ← Click CLI: prism serve / ui / crystallize / hook
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── session_reader.py  ← Read ~/.claude/projects/ JSONL files
│   │   └── git_reader.py      ← Read git diff + log via subprocess
│   ├── extraction/
│   │   ├── __init__.py
│   │   └── extractor.py       ← kg-gen integration, chunking, triple output
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py              ← SQLite setup, schema, migrations
│   │   └── models.py          ← Triple and Edge dataclasses
│   ├── linking/
│   │   ├── __init__.py
│   │   └── linker.py          ← Embed triples, find similar, create edges, staleness
│   ├── constitution/
│   │   ├── __init__.py
│   │   └── generator.py       ← Score triples → Haiku → write CLAUDE.md etc.
│   ├── server/
│   │   ├── __init__.py
│   │   ├── mcp_server.py      ← FastMCP server with 3 tools
│   │   └── ui_server.py       ← FastAPI + Pyvis UI at localhost:7823
│   └── config.py              ← Paths, constants, env vars (ANTHROPIC_API_KEY etc.)
└── tests/
    └── ...
```

**Note on the current ingestion/session_reader.py:** This file is outside the `prism_mem/` package. Move it to `prism_mem/ingestion/session_reader.py` when setting up the package structure.

---

## Tech Stack — Do Not Deviate

| Layer | Tool | Reason |
|---|---|---|
| Triple extraction | `kg-gen` | Already built, LLM + clustering, do not re-implement |
| Vector storage | `sqlite-vec` | Local-first, no cloud, no ChromaDB |
| In-memory graph | `networkx` | Interops directly with kg-gen output |
| Graph visualization | `pyvis` | Generates self-contained D3 HTML from NetworkX, no JS needed |
| MCP server | `fastmcp` | uvx-friendly, decorator-based |
| Web UI | `fastapi` + `uvicorn` | Serves pyvis HTML + constitution at localhost:7823 |
| CLI | `click` | Standard, clean |
| LLM calls | `anthropic` SDK | Haiku for extraction + constitution generation |

No Memorix dependency. No LangChain. No ChromaDB. No cloud services. Everything runs locally.

---

## Key Decisions — Do Not Second-Guess These

**Local-first.** All data lives in `~/.prism/`. No network calls except to the Anthropic API. Users own their data.

**sqlite-vec, not ChromaDB.** One file, no server, no Docker. sqlite-vec is a SQLite extension that adds vector similarity search. It is sufficient for this use case.

**kg-gen for extraction.** Do not write a custom triple extractor. kg-gen handles chunking, LLM calls, and entity clustering. Trust it.

**3 MCP tools only.** `get_context`, `query_knowledge`, `crystallize`. Do not add tools. Scope is the whole point.

**Haiku for all LLM calls.** Fast and cheap. Claude Sonnet is not needed for extraction or constitution generation at this scale.

**No Memorix dependency.** Prism is completely independent. Different database, different MCP server, different storage path. They are complementary but not coupled.

**Constitution generates 3 files.** CLAUDE.md, .cursorrules, and AGENTS.md from the same triple set, formatted differently for each agent.

---

## Build Order

Follow this order. Do not skip ahead. Each phase must produce testable output before moving to the next.

1. **Project setup** — pyproject.toml, prism_mem/ package skeleton, move session_reader.py in
2. **Session reader** — decode project path, find JSONL, parse events, return clean text chunks
3. **Git reader** — subprocess calls to git, return diff + recent log as text
4. **Extraction (kg-gen)** — chunk text, call kg-gen, inspect triple quality, iterate on chunking
5. **Storage** — SQLite schema, sqlite-vec setup, store triples + embeddings
6. **Linking** — embed triples, find similar via sqlite-vec, create edges, stale detection
7. **Constitution generator** — score triples, call Haiku, write CLAUDE.md / .cursorrules / AGENTS.md
8. **CLI** — `prism crystallize` wires phases 2–7 end to end
9. **Git hook** — `prism hook install` writes the post-commit hook
10. **MCP server** — FastMCP with 3 tools
11. **Graph UI** — FastAPI + Pyvis, 3 routes: /graph, /memory, /constitution

Phase 4 is the critical validation gate. If kg-gen produces poor-quality triples from real Claude Code sessions, the entire write path needs to change. Do not build phases 5–11 before validating phase 4 output on real data.

---

## What Prism Is Not

- Not a memory store (Memorix does that)
- Not a retrieval system (agentmemory does that)
- Not a multi-agent orchestrator
- Not a team coordination tool
- Not a chat interface
- Not a cloud service

If a feature request does not directly serve "read session → extract triples → regenerate constitution," it does not belong in the v1 scope.

---

## Environment

- Python 3.13
- Virtual env at `.venv/`
- Requires `ANTHROPIC_API_KEY` in environment

## Current State

**Phases complete: 1, 2. Next: Phase 3 (git reader).**

### Phase 1 — Done
- `pyproject.toml` created with all deps and `prism` entry point
- `prism_mem/` package with full directory skeleton (all subdirs + `__init__.py` stubs)
- `prism_mem/config.py` — paths, constants, model names
- `prism_mem/cli.py` — stub Click commands: `crystallize`, `serve`, `ui`, `hook install/uninstall`
- `prism_mem/storage/models.py` — `Triple` and `Edge` dataclasses
- All other module stubs created (raise `NotImplementedError`)
- `pip install -e .` works; `prism --help` shows all commands

### Phase 2 — Done
- `prism_mem/ingestion/session_reader.py` fully implemented
- Functions: `encode_project_path`, `find_project_sessions`, `list_sessions`, `parse_jsonl`, `parse_session`, `read_latest_session`, `read_session_by_id`
- Output chunk schema: `{role, content_type, content, timestamp, session_id, source}`
- Includes subagent transcripts (`<uuid>/subagents/*.jsonl`) tagged with `source=<agent-id>`
- Filters: user text, assistant text, assistant thinking, summary events — skips tool_use/tool_result/system noise
- Verified on real sessions: 36 chunks from latest prism-mem session including subagent

### Not yet started
- Phase 3: `prism_mem/ingestion/git_reader.py`
- Phase 4: `prism_mem/extraction/extractor.py` (kg-gen)
- Phase 5: `prism_mem/storage/db.py`
- Phase 6: `prism_mem/linking/linker.py`
- Phase 7: `prism_mem/constitution/generator.py`
- Phase 8: CLI wire-up
- Phase 9: Git hook
- Phase 10: MCP server
- Phase 11: Graph UI
