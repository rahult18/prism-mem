import json
from pathlib import Path

from prism_mem.config import CLAUDE_PROJECTS_DIR


def encode_project_path(project_path: str) -> str:
    return str(Path(project_path).resolve()).replace("/", "-")


def find_project_sessions(project_path: str) -> Path:
    encoded = encode_project_path(project_path)
    sessions_dir = CLAUDE_PROJECTS_DIR / encoded
    if not sessions_dir.exists():
        raise FileNotFoundError(f"No Claude sessions found for project: {project_path!r} (looked in {sessions_dir})")
    return sessions_dir


def list_sessions(project_path: str) -> list[Path]:
    sessions_dir = find_project_sessions(project_path)
    files = list(sessions_dir.glob("*.jsonl"))
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def _extract_blocks(event: dict, source: str) -> list[dict]:
    """Extract text/thinking chunks from a single JSONL event dict."""
    event_type = event.get("type")
    session_id = event.get("sessionId", "")
    timestamp = event.get("timestamp", "")
    chunks = []

    if event_type == "user":
        content = event.get("message", {}).get("content", "")
        if isinstance(content, str):
            text = content.strip()
            if text:
                chunks.append({
                    "role": "user",
                    "content_type": "text",
                    "content": text,
                    "timestamp": timestamp,
                    "session_id": session_id,
                    "source": source,
                })
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = block.get("text", "").strip()
                    if text:
                        chunks.append({
                            "role": "user",
                            "content_type": "text",
                            "content": text,
                            "timestamp": timestamp,
                            "session_id": session_id,
                            "source": source,
                        })
                # skip tool_result, image, and other block types

    elif event_type == "assistant":
        content = event.get("message", {}).get("content", [])
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                text = block.get("text", "").strip()
                if text:
                    chunks.append({
                        "role": "assistant",
                        "content_type": "text",
                        "content": text,
                        "timestamp": timestamp,
                        "session_id": session_id,
                        "source": source,
                    })
            elif btype == "thinking":
                text = block.get("thinking", "").strip()
                if text:
                    chunks.append({
                        "role": "assistant",
                        "content_type": "thinking",
                        "content": text,
                        "timestamp": timestamp,
                        "session_id": session_id,
                        "source": source,
                    })
            # skip tool_use and other block types

    elif event_type == "summary":
        # Produced by context compaction. Field is either "summary" or "content".
        text = (event.get("summary") or event.get("content") or "").strip()
        if text:
            chunks.append({
                "role": "assistant",
                "content_type": "summary",
                "content": text,
                "timestamp": timestamp,
                "session_id": session_id,
                "source": source,
            })

    return chunks


def parse_jsonl(jsonl_path: Path, source: str) -> list[dict]:
    chunks = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunks.extend(_extract_blocks(event, source))
    return chunks


def parse_session(jsonl_path: Path) -> list[dict]:
    chunks = parse_jsonl(jsonl_path, source="main")

    # Include subagent transcripts from <uuid>/subagents/*.jsonl
    subagents_dir = jsonl_path.parent / jsonl_path.stem / "subagents"
    if subagents_dir.exists():
        subagent_files = sorted(subagents_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        for sub_path in subagent_files:
            agent_id = sub_path.stem
            chunks.extend(parse_jsonl(sub_path, source=agent_id))

    return chunks


def read_latest_session(project_path: str) -> list[dict]:
    sessions = list_sessions(project_path)
    if not sessions:
        raise FileNotFoundError(f"No session files found for project: {project_path!r}")
    return parse_session(sessions[0])


def read_session_by_id(project_path: str, session_id: str) -> list[dict]:
    sessions_dir = find_project_sessions(project_path)
    jsonl_path = sessions_dir / f"{session_id}.jsonl"
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Session {session_id!r} not found in {sessions_dir}")
    return parse_session(jsonl_path)

if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    chunks = read_latest_session(project)
    for c in chunks:
        print(f"[{c['role']}|{c['content_type']}|{c['source']}]")
        print(c['content'])
        print()