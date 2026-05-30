# CLAUDE.md

## Overview

This project implements **prism-mem**, a knowledge graph generation system that extracts structured facts from coding sessions and git history, storing them in a SQLite database with vector embeddings. Claude processes session transcripts and code diffs through multiple phases (extracting relations, linking entities, scoring triples, and generating constitutions), using the Anthropic API via LiteLLM to power the extraction pipeline while maintaining session state across subagent calls.

## Tech Stack

- **Anthropic API (Haiku)** — Powers the extraction phase; accessed via LiteLLM for standardized API calls
- **SQLite with sqlite-vec extension** — Persists the knowledge graph and enables vector similarity searches for entity linking
- **Transformer models** — Generate embeddings for entity linking using similarity thresholds
- **Python** — Core implementation language with session readers and git diff analyzers

## Architecture

The system flows through distinct phases:

- **Phase 2** (Completed) extracts initial relations from transcripts and code diffs via the `extractor`, which calls the Haiku API and produces `Graph.relations`
- **Phase 3** (current) performs entity linking by calling `link_triple()` which invokes `create_edge()`, using embeddings and similarity thresholds to connect related entities
- **Phase 4** (next) continues processing
- **Phase 7** scores triples and runs the constitution generator

**Key Components:**
- `session_reader.py` — Extracts `sessionId` from transcripts stored in `~/.claude/history.jsonl`
- `git_reader.py` — Implements `read_git_diff()` for code change extraction
- `mcp_server.py` — Server component handling tool execution
- Subagents — Generate their own `.jsonl` session files and produce `tool_result` objects
- `~/.claude/projects/` — Stores project-specific `.jsonl` files containing knowledge graph data

## Key Decisions

- **Haiku via LiteLLM** — Chose Haiku (not more expensive models) for cost-efficient extraction, accessed through LiteLLM for unified API handling
- **Vector embeddings for linking** — Entity linking uses transformer-based embeddings with configurable similarity thresholds rather than exact string matching, enabling fuzzy entity resolution
- **Multi-phase architecture** — Separated extraction (Phase 2), linking (Phase 3), scoring (Phase 7), and constitution generation (Phase 7) into distinct phases rather than single-pass processing, enabling iterative refinement
- **Session-per-subagent pattern** — Each subagent maintains its own `.jsonl` session file rather than shared state, providing isolation and auditability
- **ANTHROPIC_API_KEY authentication** — Direct API key management for Anthropic rather than OAuth, enabling programmatic automation

## Conventions

- **Phase numbering** — Phases are sequential (Phase 2 → Phase 3 → Phase 4 → Phase 7), with completion status tracked explicitly
- **File storage locations** — Session transcripts use `~/.claude/history.jsonl`, projects use `~/.claude/projects/`, and prism-mem lives at `Desktop/Projects`
- **Knowledge graph facts** — Represented as (subject) [predicate] (object) tuples in `Graph.relations`
- **JSON session format** — Session files store transcripts as `.jsonl` with optional `attachment` fields for binary data
- **Role-based access** — System distinguishes between user roles and agent capabilities via the `(role) [can be] (user)` pattern