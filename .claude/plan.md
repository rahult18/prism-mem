# Prism — Build Plan

Each phase has a clear completion test. Do not move to the next phase until the current one passes its test.

---

## Phase 1 — Project Setup ✅ DONE

**Goal:** A proper Python package that can be installed and run as a CLI.

**What to do:**
- Create `pyproject.toml` with package metadata, dependencies, and the `prism` entry point
- Create `prism_mem/` directory with `__init__.py`
- Create all subdirectory stubs: `ingestion/`, `extraction/`, `storage/`, `linking/`, `constitution/`, `server/`
- Move `ingestion/session_reader.py` into `prism_mem/ingestion/session_reader.py`
- Create `prism_mem/config.py` for paths and constants
- Create `prism_mem/cli.py` with stub Click commands: `crystallize`, `serve`, `ui`, `hook`

**Done when:**
- `pip install -e .` works with no errors
- `prism --help` runs and shows the available commands
- All stub commands run without crashing (they can just print "not implemented yet")

---

## Phase 2 — Session Reader ✅ DONE

**Goal:** Given a project path, find and parse the most recent Claude Code session into clean text chunks.

**What to do:**
- Implement the project path encoder (slashes → hyphens)
- Implement the session directory finder: look in `~/.claude/projects/<encoded-path>/`
- List JSONL files sorted by modification time (newest first)
- Parse JSONL: one JSON object per line
- Extract text chunks from `type: "assistant"` events: pull `text` blocks and `thinking` blocks from `message.content`
- Extract text chunks from `type: "user"` events: pull the user's question
- Return a list of chunks with role, type, content, and timestamp

**Done when:**
- Point it at a real project that has Claude Code sessions
- It prints the chunks cleanly: role, content preview, timestamp
- The output is readable English, not raw JSON

---

## Phase 3 — Git Reader ✅ DONE

**Goal:** Given a project path, return the last commit's diff and recent commit history as text.

**What to do:**
- Use `subprocess` to call `git diff HEAD~1 HEAD` in the project directory
- Use `subprocess` to call `git log --oneline -20`
- Handle the case where there are no commits or git is not initialized
- Return both as plain text strings

**Done when:**
- Run it against any git repo
- The diff output and log output print cleanly as text
- No crashes on edge cases (new repo, no commits, not a git repo)

---

## Phase 4 — Extraction (Critical Validation Gate) ✅ DONE

**Goal:** Feed real session text to kg-gen and evaluate the quality of the triples it returns.

**What to do:**
- Install kg-gen
- Chunk the session text (kg-gen has a per-call input limit — find it and chunk accordingly)
- Call kg-gen on each chunk with the appropriate LLM backend (Anthropic)
- Collect the NetworkX graph output
- Print every triple: subject, predicate, object

**Done when:**
- Run it on 2–3 real Claude Code sessions from different projects
- The triples are specific and meaningful (e.g., `(auth module, uses, JWT)` not `(it, does, things)`)
- Entities are being clustered correctly (same thing not appearing as 3 different node names)
- You feel confident the triples would be useful 6 months from now

**If the triples are low quality:**
- Try different chunking strategies (smaller chunks, overlap, no overlap)
- Try different kg-gen configuration options
- Try filtering the input text (assistant-only, skip tool_use, include thinking)
- Do not move to Phase 5 until you are satisfied with triple quality on real data

---

## Phase 5 — Storage ✅ DONE

**Goal:** Persist triples and their embeddings in a local SQLite database with vector search.

**What to do:**
- Install sqlite-vec
- Define the `Triple` dataclass: id, subject, predicate, object, confidence, embedding, session_id, timestamp, stale
- Define the `Edge` dataclass: from_id, to_id, edge_type, weight
- Create `~/.prism/projects/<project-hash>/graph.db` on first use
- Implement `store_triple()`: embed the triple text, store row + embedding in sqlite-vec
- Implement `get_all_triples()` and `get_triple_by_id()`

**Done when:**
- Run Phase 4 and pipe the output into storage
- Query the DB with sqlite3 CLI and verify rows are there
- Verify embeddings are stored (not null, not empty)

---

## Phase 6 — Linking ✅ DONE

**Goal:** When a new triple is stored, find related existing triples and connect them. Detect stale facts.

**What to do:**
- Implement `find_similar(triple, top_k=5)`: query sqlite-vec for nearest neighbors by embedding
- Implement `create_edge(from_id, to_id, edge_type, weight)`: write to edges table
- Link triples where similarity > 0.85
- Implement staleness: before storing a new triple, check if any existing triple has the same subject and predicate but a different object — if so, set `stale = True` on the old one

**Done when:**
- Store 20+ triples from a real session
- Print all edges and verify they represent meaningful connections (JWT links to auth module, etc.)
- Manually introduce a conflicting triple and verify the old one is flagged stale

---

## Phase 7 — Constitution Generator ✅ DONE

**Goal:** Read the knowledge graph and produce a CLAUDE.md that accurately describes the project.

**What to do:**
- Score every non-stale triple: `score = recency_weight + confidence + retrieval_count`
- Take the top 30 triples by score
- Format them as a structured prompt for Claude Haiku
- Call Haiku with the prompt and receive a CLAUDE.md
- Write the output to `<project-root>/CLAUDE.md`
- Also write `.cursorrules` (same content, simpler format for Cursor)
- Also write `AGENTS.md` (same content, Codex format)

**Done when:**
- Run it against a project you've been working in with Claude Code
- Open the generated CLAUDE.md
- The content is accurate: it correctly identifies your tech stack, conventions, and key decisions
- You would actually find it useful if you started a new session with it loaded

This is the payoff moment. If the generated constitution is good, everything is working.

---

## Phase 8 — CLI (End-to-End Wire-Up)

**Goal:** `prism crystallize` runs the full pipeline from ingestion to constitution in one command.

**What to do:**
- Wire `prism crystallize --project <path>` to: read session → read git → extract → store → link → generate
- Add a `--session <id>` flag to target a specific session instead of the most recent one
- Print progress to stdout: "Reading session...", "Extracting triples...", "Generated CLAUDE.md"
- Handle errors gracefully: missing sessions, no git repo, API errors

**Done when:**
- Run `prism crystallize` in any project that has Claude Code sessions
- CLAUDE.md, .cursorrules, and AGENTS.md appear (or are updated) in the project root
- The whole pipeline takes under 60 seconds

---

## Phase 9 — Git Hook

**Goal:** Prism runs automatically after every commit without the user thinking about it.

**What to do:**
- Implement `prism hook install`: write `.git/hooks/post-commit` in the current project
- The hook calls `prism crystallize --project $(git rev-parse --show-toplevel)` in the background (`&`)
- Implement `prism hook uninstall`: remove the hook

**Done when:**
- Install the hook in a test repo
- Make a commit
- Within 60 seconds, CLAUDE.md is updated without you doing anything

---

## Phase 10 — MCP Server

**Goal:** Any agent that supports MCP can call Prism's 3 tools.

**What to do:**
- Implement FastMCP server in `server/mcp_server.py`
- Tool 1: `get_context()` — returns the current CLAUDE.md content for the project
- Tool 2: `query_knowledge(question: str)` — embeds the question, queries sqlite-vec, returns top-5 matching triples as structured text
- Tool 3: `crystallize(session_id: str = None)` — triggers the full pipeline, returns confirmation
- Wire `prism serve` CLI command to start the FastMCP server in stdio mode

**Done when:**
- Add Prism to Claude Code: `claude mcp add prism -- prism serve`
- Start a new Claude Code session in a project
- Call `get_context()` via Claude Code and verify it returns the correct CLAUDE.md
- Call `query_knowledge("how does auth work")` and verify it returns relevant triples

---

## Phase 11 — Graph UI

**Goal:** `prism ui` opens a local browser UI where the user can explore the knowledge graph.

**What to do:**
- Implement FastAPI app in `server/ui_server.py`
- Route `/graph`: load graph.db into NetworkX, render with Pyvis, serve the HTML
- Route `/memory`: serve a searchable table of all triples (HTML, no JS framework needed)
- Route `/constitution`: serve current CLAUDE.md content with a "Regenerate" button that calls the constitution generator
- Wire `prism ui` CLI command to start uvicorn and open `http://localhost:7823` in the browser

**Done when:**
- Run `prism ui`
- Browser opens at localhost:7823
- The force-directed graph is visible and interactive (draggable nodes, hoverable edges)
- The constitution tab shows the current CLAUDE.md with a working Regenerate button

---

## Shipping

**When all 11 phases pass their tests:**
- Finalize `pyproject.toml` (version 0.1.0, correct classifiers, description)
- Write `README.md`: one-liner, 3-command quickstart, architecture diagram, link to PyPI
- `uv build` + `uv publish` to PyPI
- Test `uvx prism-mem serve` from a fresh environment (no install needed)
- Add to Claude Code: `claude mcp add prism -- uvx prism-mem serve`

---

## Scope Rules

If it is not in the 11 phases above, it is not in v1. Specifically:

- No multi-agent orchestration
- No team features
- No cloud sync or remote storage
- No chat interface
- No Memorix integration (that is v2 if ever)
- No support for agents other than Claude Code for ingestion (Cursor/Codex use the MCP read path, not ingestion)

The v1 goal is: one user, one machine, any agent that speaks MCP, automatic context regeneration after every commit.
