import json
import os
from pathlib import Path

session_dir = Path.home() / ".claude"


def find_session_dir() -> Path:
    return session_dir
