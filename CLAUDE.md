# CLAUDE.md

## Overview

Prism-mem is a knowledge graph generation and memory system that processes coding sessions into structured semantic relationships. It ingests session data from JSONL archives, extracts triples using sentence transformers for semantic understanding, links entities based on similarity thresholds, and stores the resulting knowledge graph with weighted edges in SQLite. The system enables AI agents to understand and reason over project history and context.

## Tech Stack

- **sentence-transformers/all-MiniLM-L6-v2**: Embedding model for semantic similarity—chosen for lightweight inference and effective comparison at the 0.85 similarity threshold
- **SQLite** (db.py): Persistent storage for the knowledge graph with embedding support
- **NetworkX** (pyproject.toml): Graph data structure and operations for relations representation
- **FastAPI** (requirements.txt): HTTP interface for the system
- **JSONL format**: Append-only session logging—supports efficient streaming and archival of session records

## Architecture

The system flows through distinct phases:

- **Ingestion** (session_reader.py): Reads JSONL session archives and filters tool-results, extracting sessionId and other structured fields
- **Knowledge Graph Generation** (kg-gen phase in phase/): Implemented by extractor.py, which generates Graph.relations from session data
- **Entity Linking** (linker.py): Implements link_triple, which calls create_edge to connect extracted triples; ingest_triple orchestrates the linking
- **Storage** (prism_mem/storage + db.py): Persists the knowledge graph with weighted edges in SQLite
- **Configuration** (config.py): Defines paths; sessions_dir is computed from project_path

Phases are sequential with status tracking (marked DONE when complete).

## Key Decisions

- **L2 Distance Threshold of 0.5477**: Maps to the 0.85 SIMILARITY_THRESHOLD for determining whether entities should be linked—provides a principled cutoff for semantic equivalence
- **Weighted Edges**: Relations in the graph carry weight rather than being unweighted—preserves confidence or frequency information from the extraction process
- **JSONL over Structured DB for Sessions**: Session archives use append-only JSONL to support real-time logging and immutable history
- **UUID-based Organization**: UUID folders contain subagents, organizing work by session identity rather than agent type

## Conventions

- **Phase Naming**: Phases are referenced by name (e.g., "phase") with explicit status fields (DONE, in progress)
- **Path Computation**: Derived paths (sessions_dir) are computed from a root project_path at startup (config.py)
- **Triple-centric Flow**: Data moves through extract → ingest_triple → link_triple → create_edge, with each step adding semantic structure
- **Session Fields**: JSONL records include sessionId as a primary identifier for grouping and traceability
- **Documentation**: context.md documents the overall system; CLAUDE.md documents individual phases