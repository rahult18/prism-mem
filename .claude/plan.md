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

**Goal:** Persist triples and their embeddings in a local SQLite database.

**What to do:**
- Define the `Triple` dataclass: id, subject, predicate, object, confidence, session_id, timestamp, stale
- Define the `Edge` dataclass: from_id, to_id, edge_type, weight
- Create `~/.prism/projects/<project-hash>/graph.db` on first use
- Implement `store_triple()`: embed the triple text, store row in `triples` + embedding blob in `embeddings`
- Implement `get_all_triples()` and `get_triple_by_id()`

**Done when:**
- Run Phase 4 and pipe the output into storage
- Query the DB with sqlite3 CLI and verify rows are there
- Verify embeddings are stored (not null, not empty)

---

## Phase 6 — Linking ✅ DONE

**Goal:** When a new triple is stored, find related existing triples and connect them. Detect stale facts.

**What to do:**
- Implement `search_similar(conn, query_bytes, top_k, exclude_id)`: load all embeddings, numpy cosine similarity (matrix dot product on normalized vectors), return top-k above threshold
- Implement `find_similar(conn, triple_id, top_k)`: thin wrapper over `search_similar` using the stored embedding for that triple
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

## Phase 8 — CLI (End-to-End Wire-Up) ✅ DONE

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

## Phase 9 — Git Hook ✅ DONE

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

## Phase 10 — MCP Server ✅ DONE

**Goal:** Any agent that supports MCP can call Prism's 3 tools.

**What to do:**
- Implement FastMCP server in `server/mcp_server.py`
- Tool 1: `get_context()` — returns the current CLAUDE.md content for the project
- Tool 2: `query_knowledge(question: str)` — embeds question, runs `search_similar` from `linker.py` (numpy cosine), returns top-5 matching triples as structured text
- Tool 3: `crystallize(session_id: str = None)` — triggers the full pipeline, returns confirmation
- Wire `prism serve` CLI command to start the FastMCP server in stdio mode

**Done when:**
- Add Prism to Claude Code: `claude mcp add prism -- prism serve`
- Start a new Claude Code session in a project
- Call `get_context()` via Claude Code and verify it returns the correct CLAUDE.md
- Call `query_knowledge("how does auth work")` and verify it returns relevant triples

---

## Phase 11 — Graph UI ✅ DONE

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

**Enhancements added post-completion (see Post-Shipping section):**
- `/memory`: Session column with hover for full ID
- `/graph`: Node-click sidebar showing contributing sessions with active/stale status
- `/constitution`: Copy button with clipboard feedback

---

## Shipping

**When all 11 phases pass their tests:**
- Finalize `pyproject.toml` (version 0.1.0, correct classifiers, description)
- Write `README.md`: one-liner, 3-command quickstart, architecture diagram, link to PyPI
- `uv build` + `uv publish` to PyPI
- Test `uvx prism-mem serve` from a fresh environment (no install needed)
- Add to Claude Code: `claude mcp add prism -- uvx prism-mem serve`

---

## Post-Shipping Enhancements

Work completed after all 11 phases. None of these change the DB schema or add new routes.

### Multi-provider LLM config ✅ DONE
- `~/.prism/config.toml` stores `provider`, `model`, `api_key` (flat TOML, built-in `tomllib`)
- `config.py` exports `load_config`, `save_config`, `get_model_string` (`provider/model`), `get_api_key`, `is_config_complete`, `validate_provider` (uses `litellm.provider_list`)
- `generator.py` switched from `anthropic.Anthropic` client to `litellm.completion()`; response via `response.choices[0].message.content`
- `extractor.py` uses `get_model_string()` / `get_api_key()` — kg-gen/dspy.LM already speaks LiteLLM format
- `cli.py` adds `prism config set {provider|model|api-key}` (provider validated at set-time) and `prism config show` (api-key masked)
- `crystallize` now checks `is_config_complete()` with actionable error instead of crashing on missing env var
- `pyproject.toml`: removed `anthropic` direct dep, added `litellm>=1.0.0`

### Code review fixes ✅ DONE
- Removed unused `timezone` import in `generator.py`
- Removed dead `_CURATED_PROVIDERS` in `config.py`, `_VALID_KEYS` in `cli.py`
- `ui_server.py` `/constitution/regenerate` now returns error page instead of silently swallowing exceptions
- `mcp_server.py` `crystallize` tool checks `is_config_complete()` before spawning subprocess

### numpy migration ✅ DONE
- Removed `sqlite-vec` dependency (SQLite extension requiring `enable_load_extension`, disabled in many Python builds)
- Added plain `embeddings` table to SQLite schema; `vec_from_bytes()` helper in `db.py`
- `linker.py`: new `search_similar(conn, query_bytes, top_k, exclude_id)` using numpy matrix dot product; `find_similar` delegates to it; `mcp_server.query_knowledge` also uses it
- `pyproject.toml`: removed `sqlite-vec`, added `numpy>=1.24.0`
- Works on any Python build (pyenv, system Python, Docker, etc.)

### Improved CLI logging ✅ DONE
- `prism crystallize` shows per-step elapsed time after each phase
- Expected chunk count displayed before the extraction API call so user knows what's coming
- `click.progressbar` with live `N/total` counter during store/link loop
- Constitution step shows file names as they're written

### Rich CLI overhaul ✅ DONE
- Replaced flat `click.echo` output with `rich`-powered 5-phase display
- Each phase: spinner via `console.status(...)` while running → permanent `✔ N/5 PhaseName  detail  Xs` line when done
- Phase 4 (Store+Link): `rich.progress.Progress` with `BarColumn` + `MofNCompleteColumn`, `transient=True` so bar disappears and is replaced by the ✔ line
- Noise suppressed: `logging.getLogger("LiteLLM/huggingface_hub/sentence_transformers").setLevel(ERROR)`, `HF_HUB_DISABLE_PROGRESS_BARS=1`, `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`, `warnings.filterwarnings(ignore, unauthenticated)`
- Embedding model pre-warmed via `_get_model()` before phase display so any load output appears cleanly before UI
- `pyproject.toml`: added `rich>=13.0.0`

### Incremental extraction caching ✅ DONE
- Watermark approach: track last-processed session timestamp + processed git commit hashes in DB
- `session_watermarks (session_key TEXT PK, last_timestamp TEXT)` — one row per JSONL file stem
- `processed_commits (commit_hash TEXT PK, processed_at TEXT)` — one row per HEAD commit
- `db.py`: `get_session_watermark`, `set_session_watermark`, `is_commit_processed`, `mark_commit_processed`
- `git_reader.py`: `read_git_head()` via `git rev-parse HEAD`
- `cli.py`: session chunks filtered to `timestamp > last_ts`; git diff skipped if commit already processed; combined text built from new-only content; if empty → exit early with "Nothing new since last run"
- Phase 1 display shows `(N new, M cached)` when a watermark exists
- Watermarks advanced only after successful store+link (atomic with triple storage)
- DB opened once at run start, closed after watermarks updated

### Clustering fallback ✅ DONE
- `extractor.py`: `kg.generate(cluster=True)` wrapped in try/except
- On exception (typically Pydantic `literal_error` when LLM returns integer instead of entity string), retries with `cluster=False`
- Triples are still fully extracted; only cross-chunk entity normalization is skipped
- Downstream cosine similarity linking in Phase 4 handles entity deduplication regardless

### UI enhancements ✅ DONE
- `/memory`: added `Session` column after `Timestamp` — 8-char truncation with full ID in `title` attribute
- `/graph`: node click opens a fixed sidebar listing contributing session IDs with active/stale badges. Node info built server-side from all triples (including stale), embedded as JSON, accessed via injected vis.js `network.on('click', ...)` listener. `</` escaped to `<\/` in embedded JSON.
- `/constitution`: added `Copy` button beside Regenerate. Reads `pre.innerText` via `navigator.clipboard.writeText`, label swaps to `Copied!` for 1.5s then restores.

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
