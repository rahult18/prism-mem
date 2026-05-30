import sys
import time

import click

from prism_mem.config import is_config_complete


@click.group()
def cli():
    """Prism — post-session knowledge crystallizer for AI coding agents."""


@cli.command()
@click.option("--project", default=".", show_default=True, help="Path to the project root.")
@click.option("--session", default=None, help="Specific session ID to process (default: most recent).")
def crystallize(project, session):
    """Read the last session + git history, extract triples, regenerate constitution files."""
    from datetime import datetime

    from prism_mem.constitution.generator import write_constitution
    from prism_mem.extraction.extractor import extract_triples
    from prism_mem.ingestion.git_reader import read_git_diff, read_git_log
    from prism_mem.ingestion.session_reader import read_latest_session, read_session_by_id
    from prism_mem.linking.linker import ingest_triple
    from prism_mem.storage.db import open_db
    from prism_mem.storage.models import Triple

    if not is_config_complete():
        click.echo("Error: prism is not configured. Run: prism config set provider <name>", err=True)
        click.echo("       then: prism config set model <model-name>", err=True)
        click.echo("       then: prism config set api-key <your-key>", err=True)
        sys.exit(1)

    t0 = time.time()

    # 1. Read session
    click.echo("Reading session...")
    try:
        if session:
            chunks = read_session_by_id(project, session)
        else:
            chunks = read_latest_session(project)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    session_id = chunks[0]["session_id"] if chunks else "unknown"
    session_text = "\n\n".join(
        f"[{c['role']}] {c['content']}"
        for c in chunks
        if c["content_type"] in ("text", "summary")
    )
    click.echo(f"  {len(chunks)} chunks from session {session_id[:8]}...")

    # 2. Read git
    click.echo("Reading git history...")
    git_log = read_git_log(project)
    git_diff = read_git_diff(project)
    git_text = "\n\n".join(filter(None, [git_log, git_diff]))
    if git_text:
        click.echo(f"  {len(git_log.splitlines())} commits, {len(git_diff.splitlines())} diff lines")
    else:
        click.echo("  (no git history)")

    # 3. Extract triples
    combined = "\n\n---\n\n".join(filter(None, [session_text, git_text]))
    click.echo(f"Extracting triples from {len(combined):,} chars (calling API)...")
    try:
        raw_triples = extract_triples(
            combined,
            context="Claude Code session and git history for a software project",
        )
    except Exception as e:
        click.echo(f"Error during extraction: {e}", err=True)
        sys.exit(1)
    click.echo(f"  {len(raw_triples)} triples extracted")

    # 4. Store + link
    click.echo("Storing and linking triples...")
    conn = open_db(project)
    stored = 0
    for subj, pred, obj in raw_triples:
        t = Triple(
            subject=subj,
            predicate=pred,
            object=obj,
            session_id=session_id,
            timestamp=datetime.utcnow(),
        )
        ingest_triple(conn, t)
        stored += 1
    conn.close()
    click.echo(f"  {stored} triples stored")

    # 5. Generate constitution
    click.echo("Generating constitution files...")
    try:
        written = write_constitution(project)
    except Exception as e:
        click.echo(f"Error during constitution generation: {e}", err=True)
        sys.exit(1)

    elapsed = time.time() - t0
    click.echo(f"\nDone in {elapsed:.1f}s:")
    for name, path in written.items():
        click.echo(f"  {path}  ({path.stat().st_size} bytes)")


@cli.command()
@click.option("--project", default=".", show_default=True, help="Path to the project root.")
def serve(project):
    """Start the MCP server in stdio mode (for use with `claude mcp add`)."""
    from prism_mem.server.mcp_server import start_mcp_server
    start_mcp_server(project)


@cli.command()
@click.option("--project", default=".", show_default=True, help="Path to the project root.")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7823, show_default=True)
@click.option("--no-browser", is_flag=True, default=False, help="Don't open the browser automatically.")
def ui(project, host, port, no_browser):
    """Start the graph UI at http://localhost:7823."""
    from prism_mem.server.ui_server import start_ui_server

    url = f"http://{host}:{port}"
    click.echo(f"Starting Prism UI at {url}")
    start_ui_server(project, host=host, port=port, open_browser=not no_browser)


@cli.group()
def hook():
    """Manage the git post-commit hook."""


_PRISM_MARKER_START = "# >>> prism-mem"
_PRISM_MARKER_END = "# <<< prism-mem"
_HOOK_SNIPPET = """\
# >>> prism-mem
prism crystallize --project "$(git rev-parse --show-toplevel)" &
# <<< prism-mem"""


@hook.command("install")
@click.option("--project", default=".", show_default=True, help="Path to the project root.")
def hook_install(project):
    """Install the post-commit hook in the given project."""
    import stat
    from pathlib import Path

    project_path = Path(project).resolve()
    git_dir = project_path / ".git"
    if not git_dir.is_dir():
        click.echo(f"Error: no .git directory found in {project_path}", err=True)
        sys.exit(1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_file = hooks_dir / "post-commit"

    if hook_file.exists():
        content = hook_file.read_text()
        if _PRISM_MARKER_START in content:
            click.echo("prism hook already installed.")
            return
        # Append to existing hook
        new_content = content.rstrip("\n") + "\n\n" + _HOOK_SNIPPET + "\n"
        hook_file.write_text(new_content)
    else:
        hook_file.write_text("#!/bin/sh\n\n" + _HOOK_SNIPPET + "\n")

    # Ensure executable
    current = hook_file.stat().st_mode
    hook_file.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    click.echo(f"Installed prism post-commit hook at {hook_file}")


@cli.group()
def config():
    """Manage prism configuration (provider, model, api-key)."""


_VALID_KEYS = ("provider", "model", "api-key")
_CURATED_PROVIDERS = [
    "anthropic", "openai", "gemini", "ollama", "groq",
    "mistral", "together_ai", "bedrock", "azure", "cohere",
]


@config.command("set")
@click.argument("key", metavar="KEY", type=click.Choice(["provider", "model", "api-key"], case_sensitive=False))
@click.argument("value")
def config_set(key, value):
    """Set a config value. KEY is one of: provider, model, api-key."""
    from prism_mem.config import load_config, save_config, validate_provider

    if key == "provider":
        if not validate_provider(value):
            click.echo(f"Error: '{value}' is not a recognized provider.", err=True)
            click.echo(f"Common providers: {', '.join(_CURATED_PROVIDERS)}", err=True)
            sys.exit(1)

    cfg = load_config()
    cfg_key = "api_key" if key == "api-key" else key
    cfg[cfg_key] = value
    save_config(cfg)
    display = "***" if key == "api-key" else value
    click.echo(f"Set {key} = {display}")


@config.command("show")
def config_show():
    """Show current prism configuration."""
    from prism_mem.config import load_config

    cfg = load_config()
    if not cfg:
        click.echo("No configuration found. Run: prism config set provider <name>")
        return

    provider = cfg.get("provider", "(not set)")
    model = cfg.get("model", "(not set)")
    api_key = cfg.get("api_key", "")
    if api_key:
        masked = api_key[:8] + "***" if len(api_key) > 8 else "***"
    else:
        masked = "(not set)"

    click.echo(f"provider = {provider}")
    click.echo(f"model    = {model}")
    click.echo(f"api-key  = {masked}")


@hook.command("uninstall")
@click.option("--project", default=".", show_default=True, help="Path to the project root.")
def hook_uninstall(project):
    """Remove the post-commit hook from the given project."""
    from pathlib import Path

    project_path = Path(project).resolve()
    hook_file = project_path / ".git" / "hooks" / "post-commit"

    if not hook_file.exists():
        click.echo("No post-commit hook found.")
        return

    content = hook_file.read_text()
    if _PRISM_MARKER_START not in content:
        click.echo("prism hook not found in post-commit hook.")
        return

    # Strip prism block (start marker through end marker, inclusive)
    lines = content.splitlines(keepends=True)
    filtered = []
    inside = False
    for line in lines:
        if line.strip() == _PRISM_MARKER_START:
            inside = True
            continue
        if line.strip() == _PRISM_MARKER_END:
            inside = False
            continue
        if not inside:
            filtered.append(line)

    remaining = "".join(filtered).rstrip("\n") + "\n"

    # If only the shebang (or blank) remains, remove the file
    non_empty = [l for l in remaining.splitlines() if l.strip() and not l.strip().startswith("#!")]
    if not non_empty:
        hook_file.unlink()
        click.echo("Removed post-commit hook (file was only prism).")
    else:
        hook_file.write_text(remaining)
        click.echo(f"Removed prism block from {hook_file}")
