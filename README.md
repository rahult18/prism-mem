# prism-mem

**Every coding session leaves behind artifacts. Prism reads them and turns them into structured, reusable knowledge — automatically.**

Prism is a post-session knowledge crystallizer for AI coding agents. It reads Claude Code session transcripts and git history, extracts semantic knowledge as triples, links them into a graph, and auto-regenerates the context files every agent reads at session start (`CLAUDE.md`, `.cursorrules`, `AGENTS.md`).

## Quickstart

```bash
pip install prism-mem

# Configure your LLM provider (one-time setup)
prism config set provider anthropic
prism config set model claude-haiku-4-5-20251001
prism config set api-key <your-api-key>

# Run once after a coding session to extract knowledge and regenerate context files
prism crystallize --project /path/to/your/project

# Install the git hook so it runs automatically after every commit
prism hook install --project /path/to/your/project

# Add as an MCP server so agents can query the knowledge graph directly
claude mcp add prism -- prism serve --project /path/to/your/project
```

## Configuration

Prism uses `~/.prism/config.toml` to store your LLM provider settings. Set it up with:

```bash
prism config set provider anthropic        # or: openai, gemini, ollama, groq, mistral, ...
prism config set model claude-haiku-4-5-20251001
prism config set api-key <your-api-key>

prism config show                          # verify (api-key is masked)
```

The `provider` is validated against LiteLLM's provider list at set-time. Any provider LiteLLM supports works — Anthropic, OpenAI, Gemini, local Ollama models, etc. The model string is passed as `provider/model` to LiteLLM.

## How it works

```
[git commit]
     │
     ▼
[1] INGEST
    Read ~/.claude/projects/<id>/<session>.jsonl  +  git diff HEAD~1 HEAD
     │
     ▼
[2] EXTRACT
    kg-gen → NetworkX graph of (subject, predicate, object) triples
     │
     ▼
[3] STORE + LINK
    Embed triples (sentence-transformers, local)
    Store in SQLite + sqlite-vec at ~/.prism/projects/<hash>/graph.db
    Connect related triples by cosine similarity
    Flag contradicted facts as stale
     │
     ▼
[4] GENERATE
    Score triples (recency + confidence)
    Top 30 → LLM (via LiteLLM) → write CLAUDE.md / .cursorrules / AGENTS.md
```

## Commands

| Command | What it does |
|---|---|
| `prism config set <key> <value>` | Set provider, model, or api-key |
| `prism config show` | Show current config (api-key masked) |
| `prism crystallize --project .` | Full pipeline: ingest → extract → store → generate |
| `prism hook install --project .` | Write `.git/hooks/post-commit` to run crystallize after every commit |
| `prism hook uninstall --project .` | Remove the hook |
| `prism serve --project .` | Start MCP server in stdio mode |
| `prism ui --project .` | Open graph UI at `http://localhost:7823` |

## MCP tools

When added as an MCP server, Prism exposes three tools to any agent:

| Tool | What it does |
|---|---|
| `get_context()` | Returns the current `CLAUDE.md` for the project |
| `query_knowledge(question)` | Semantic search over the triple graph, returns top-5 matches |
| `crystallize(session_id?)` | Triggers the full pipeline in the background |

## Graph UI

`prism ui` opens a local browser UI at `http://localhost:7823`:

- **/constitution** — current `CLAUDE.md` with a Regenerate button
- **/memory** — searchable table of all triples (active + stale)
- **/graph** — interactive force-directed knowledge graph

## Storage

All data is local. Nothing leaves your machine except calls to your configured LLM provider.

```
~/.prism/
├── config.toml             ← provider, model, api-key
└── projects/
    └── <project-hash>/
        └── graph.db        ← SQLite + sqlite-vec, one file per project
```

## Requirements

- Python 3.13+
- Any LiteLLM-compatible LLM provider (configured via `prism config set`)

## License

MIT
