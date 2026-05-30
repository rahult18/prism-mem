import tomllib
from pathlib import Path

PRISM_HOME = Path.home() / ".prism"
PROJECTS_DIR = PRISM_HOME / "projects"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

_CONFIG_PATH = PRISM_HOME / "config.toml"

SIMILARITY_THRESHOLD = 0.85
TOP_TRIPLES_FOR_CONSTITUTION = 30

UI_HOST = "127.0.0.1"
UI_PORT = 7823

_CURATED_PROVIDERS = [
    "anthropic", "openai", "gemini", "ollama", "groq",
    "mistral", "together_ai", "bedrock", "azure", "cohere",
]


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    with open(_CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def save_config(cfg: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, val in cfg.items():
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key} = "{escaped}"')
    _CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_model_string() -> str:
    cfg = load_config()
    provider = cfg.get("provider", "")
    model = cfg.get("model", "")
    if not provider or not model:
        return ""
    return f"{provider}/{model}"


def get_api_key() -> str:
    return load_config().get("api_key", "")


def is_config_complete() -> bool:
    cfg = load_config()
    return bool(cfg.get("provider") and cfg.get("model") and cfg.get("api_key"))


def validate_provider(provider: str) -> bool:
    import litellm
    valid = {p.value for p in litellm.provider_list}
    return provider in valid
