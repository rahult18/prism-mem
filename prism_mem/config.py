import os
from pathlib import Path

PRISM_HOME = Path.home() / ".prism"
PROJECTS_DIR = PRISM_HOME / "projects"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SIMILARITY_THRESHOLD = 0.85
TOP_TRIPLES_FOR_CONSTITUTION = 30
EMBEDDING_MODEL = "text-embedding-3-small"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

UI_HOST = "127.0.0.1"
UI_PORT = 7823
