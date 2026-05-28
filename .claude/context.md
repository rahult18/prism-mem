# Prism — Implementation Context

Quick reference for coding agents. Read this before touching any file.

---

## What's built vs what's a stub

| File | Status | Notes |
|---|---|---|
| `prism_mem/__init__.py` | stub | just `__version__` |
| `prism_mem/config.py` | done | paths, model names, constants |
| `prism_mem/cli.py` | stub | all commands print "not implemented yet" |
| `prism_mem/ingestion/session_reader.py` | **done** | fully implemented, tested on real data |
| `prism_mem/ingestion/git_reader.py` | stub | raises NotImplementedError |
| `prism_mem/extraction/extractor.py` | stub | raises NotImplementedError |
| `prism_mem/storage/models.py` | **done** | `Triple` and `Edge` dataclasses |
| `prism_mem/storage/db.py` | stub | raises NotImplementedError |
| `prism_mem/linking/linker.py` | stub | raises NotImplementedError |
| `prism_mem/constitution/generator.py` | stub | raises NotImplementedError |
| `prism_mem/server/mcp_server.py` | stub | raises NotImplementedError |
| `prism_mem/server/ui_server.py` | stub | raises NotImplementedError |

---

## session_reader.py — public API

```python
from prism_mem.ingestion.session_reader import (
    read_latest_session,      # (project_path: str) -> list[dict]
    read_session_by_id,       # (project_path: str, session_id: str) -> list[dict]
    list_sessions,            # (project_path: str) -> list[Path]  newest first
    parse_session,            # (jsonl_path: Path) -> list[dict]
    parse_jsonl,              # (jsonl_path: Path, source: str) -> list[dict]
    encode_project_path,      # (project_path: str) -> str
    find_project_sessions,    # (project_path: str) -> Path
)
```

**Chunk schema:**
```python
{
    "role": "user" | "assistant",
    "content_type": "text" | "thinking" | "summary",
    "content": str,
    "timestamp": str,        # ISO8601
    "session_id": str,       # UUID from the JSONL line
    "source": "main" | "<agent-id>",  # "main" = top-level session, agent-id = subagent
}
```

**What's included / excluded:**
- Included: user text, assistant text, assistant thinking blocks, summary events (compaction)
- Excluded: tool_use, tool_result, file-history-snapshot, hook events, system injections
- Subagent transcripts at `<uuid>/subagents/*.jsonl` are merged in, tagged with `source=<agent-id>`

---

## config.py — key constants

```python
from prism_mem.config import (
    PRISM_HOME,               # ~/.prism
    PROJECTS_DIR,             # ~/.prism/projects
    CLAUDE_PROJECTS_DIR,      # ~/.claude/projects
    ANTHROPIC_API_KEY,        # from env
    SIMILARITY_THRESHOLD,     # 0.85
    TOP_TRIPLES_FOR_CONSTITUTION,  # 30
    HAIKU_MODEL,              # "claude-haiku-4-5-20251001"
    UI_PORT,                  # 7823
)
```

---

## storage/models.py — dataclasses

```python
@dataclass
class Triple:
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    embedding: bytes = b""
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    stale: bool = False
    id: int = 0

@dataclass
class Edge:
    from_id: int
    to_id: int
    edge_type: str
    weight: float
```

---

## Environment

- Python 3.13.5, venv at `.venv/`
- **Always run with:** `DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib .venv/bin/python`
  (macOS pyexpat linking workaround — required or imports fail)
- `ANTHROPIC_API_KEY` must be set for any LLM calls
- Package installed editable: `pip install -e .` already done

---

## Running session_reader manually

```bash
# from project root
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib .venv/bin/python prism_mem/ingestion/session_reader.py
# or pass a project path:
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib .venv/bin/python prism_mem/ingestion/session_reader.py /path/to/project
```

---

## What's next (Phase 3)

Implement `prism_mem/ingestion/git_reader.py`:
- `read_git_diff(project_path: str) -> str` — runs `git diff HEAD~1 HEAD`
- `read_git_log(project_path: str, n: int = 20) -> str` — runs `git log --oneline -N`
- Both use `subprocess.run`, cwd=project_path, handle edge cases gracefully (no commits, not a git repo)
