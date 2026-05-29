# AGENTS.md

This project is a knowledge graph generation system (prism-mem) that extracts, processes, and stores coding session data with semantic embeddings.

## Repository Layout

- **config.py** - Defines paths and configuration for the project
- **cli.py** - Implements the UI for user interaction
- **session_reader.py** - Filters tool-results from session archives
- **extractor.py** - Part of the kg-gen phase; extracts triples from sessions
- **linker.py** - Implements `link_triple()` function to create graph edges
- **db.py** - Uses SQLite and embeddings from `sentence-transformers/all-MiniLM-L6-v2`
- **pyproject.toml** - Project configuration; depends on networkx
- **requirements.txt** - Lists dependencies including fastapi
- **.jsonl files** - Support append-only logging for session archives; contain `sessionId` field
- **sessions_dir** - Computed from project_path; contains UUID folders with subagents subdirectories
- **context.md** - Documents prism-mem
- **CLAUDE.md** - Documents the extraction phase

## Build & Run

1. Install dependencies from `requirements.txt` and `pyproject.toml` (includes fastapi, networkx)
2. Configure paths via `config.py`
3. Run the CLI via `cli.py` to start the user interface
4. The kg-gen phase processes coding sessions and generates `Graph.relations`

## Rules

1. All session data must be read through `session_reader.py` to properly filter tool-results
2. Similarity matching uses `sentence-transformers/all-MiniLM-L6-v2` embeddings with a threshold of 0.85; max L2 distance allowed is 0.5477
3. Graph edges created via `linker.py` must have weight attributes
4. Session archive data is stored in JSONL format with append-only logging; always include `sessionId` field
5. The kg-gen phase is completed and generates `Graph.relations`; do not modify its status
6. Triple linking must follow the chain: `ingest_triple()` → `link_triple()` → `create_edge()`
7. All embeddings must come from the remote model `rahult18/prism-mem` or the configured transformer model in `db.py`