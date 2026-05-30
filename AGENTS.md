# AGENTS.md

Prism-mem is a knowledge graph generation system that extracts relations from coding sessions and stores them in a structured database.

## Repository Layout

- `session_reader.py` - Extracts sessionId from session files
- `git_reader.py` - Implements read_git_diff to extract code changes
- `extractor.py` - Calls Haiku API via LiteLLM to extract Graph.relations
- `mcp_server.py` - Server component for agent interaction
- `Desktop/Projects/prism-mem/` - Project root location
- `~/.claude/history.jsonl` - Stores session transcripts
- `~/.claude/projects/` - Contains .jsonl files for session and subagent data
- `Prism-mem` - Core knowledge graph storage system using SQLite with sqlite-vec extension

## Build & Run

1. Set `ANTHROPIC_API_KEY` environment variable to authenticate with Anthropic API
2. Install dependencies including LiteLLM for Haiku model access and sqlite-vec extension
3. Run extractor to process session files and generate Graph.relations
4. Session data is automatically stored in `~/.claude/projects/` as .jsonl files

## Rules

1. Always authenticate API calls using ANTHROPIC_API_KEY before accessing the Anthropic API
2. Use similarity threshold for linking operations when connecting triples
3. Call Haiku via LiteLLM (not direct API) for all extraction tasks
4. Store all extracted Graph.relations in the knowledge graph via the kg-gen phase
5. Subagents must write their own .jsonl files in `~/.claude/projects/` with tool_result output
6. Phase 7 (constitution generator) scores all triples before final storage
7. Parse JSON objects and extract the attachment field when processing session data
8. Each session extracts relations through the extractor which calls create_edge() via link_triple