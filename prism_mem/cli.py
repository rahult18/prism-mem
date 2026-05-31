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
    import logging
    import math
    import os
    import warnings
    from datetime import datetime
    from pathlib import Path

    # Suppress noisy third-party output before any imports that trigger it
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
    logging.getLogger("kg_gen").setLevel(logging.CRITICAL)
    warnings.filterwarnings("ignore", message=".*unauthenticated.*")
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_VERBOSITY"] = "error"

    from rich.console import Console
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

    from prism_mem.constitution.generator import write_constitution
    from prism_mem.extraction.extractor import CHUNK_SIZE, extract_triples
    from prism_mem.ingestion.git_reader import read_git_diff, read_git_head, read_git_log
    from prism_mem.ingestion.session_reader import (
        find_project_sessions, list_sessions, parse_session,
    )
    from prism_mem.linking.linker import ingest_triple
    from prism_mem.storage.db import (
        _get_model, open_db,
        get_session_watermark, set_session_watermark,
        is_commit_processed, mark_commit_processed,
    )
    from prism_mem.storage.models import Triple

    if not is_config_complete():
        click.echo("Error: prism is not configured. Run: prism config set provider <name>", err=True)
        click.echo("       then: prism config set model <model-name>", err=True)
        click.echo("       then: prism config set api-key <your-key>", err=True)
        sys.exit(1)

    # Pre-warm the embedding model so any load output appears before the phase UI
    _get_model()

    console = Console(highlight=False)
    project_name = Path(project).resolve().name
    console.print(f"\n[bold]Prism[/bold] [dim]—[/dim] [cyan]{project_name}[/cyan]\n")

    t0 = time.time()

    def _done(n, label, detail, elapsed):
        console.print(f"  [green]✔[/green]  [bold]{n}/5  {label:<12}[/bold] {detail}  [dim]{elapsed:.1f}s[/dim]")

    def _err(msg):
        console.print(f"  [red]✖[/red]  {msg}")
        sys.exit(1)

    # Open DB once for the whole run so watermark reads and writes are atomic
    conn = open_db(project)

    # ── Phase 1: Session ─────────────────────────────────────────────────────
    t_step = time.time()
    with console.status("  [dim]1/5  Session[/dim]  reading...", spinner="dots"):
        try:
            if session:
                sessions_dir = find_project_sessions(project)
                session_file = sessions_dir / f"{session}.jsonl"
                if not session_file.exists():
                    _err(f"session {session!r} not found")
                session_key = session
            else:
                session_files = list_sessions(project)
                if not session_files:
                    _err("no session files found")
                session_file = session_files[0]
                session_key = session_file.stem
            chunks = parse_session(session_file)
        except FileNotFoundError as e:
            conn.close()
            _err(str(e))

    # Filter to only chunks newer than the watermark for this session
    last_ts = get_session_watermark(conn, session_key)
    new_chunks = [
        c for c in chunks
        if not last_ts or not c["timestamp"] or c["timestamp"] > last_ts
    ]
    cached_count = len(chunks) - len(new_chunks)

    session_id = chunks[0]["session_id"] if chunks else "unknown"
    new_session_text = "\n\n".join(
        f"[{c['role']}] {c['content']}"
        for c in new_chunks
        if c["content_type"] in ("text", "summary")
    )

    session_detail = f"{len(chunks)} chunks · {session_id[:8]}"
    if cached_count:
        session_detail += f"  ({len(new_chunks)} new, {cached_count} cached)"
    _done(1, "Session", session_detail, time.time() - t_step)

    # ── Phase 2: Git ──────────────────────────────────────────────────────────
    t_step = time.time()
    with console.status("  [dim]2/5  Git[/dim]  reading history...", spinner="dots"):
        git_log = read_git_log(project)
        git_diff = read_git_diff(project)
        head_commit = read_git_head(project)

    git_already_processed = bool(head_commit and is_commit_processed(conn, head_commit))
    new_git_text = "" if git_already_processed else "\n\n".join(filter(None, [git_log, git_diff]))

    if git_already_processed:
        git_detail = f"{len(git_log.splitlines())} commits · already processed, skipped"
    elif new_git_text:
        git_detail = f"{len(git_log.splitlines())} commits · {len(git_diff.splitlines())} diff lines"
    else:
        git_detail = "no git history"
    _done(2, "Git", git_detail, time.time() - t_step)

    # ── Phase 3: Extract ──────────────────────────────────────────────────────
    combined = "\n\n---\n\n".join(filter(None, [new_session_text, new_git_text]))

    if not combined.strip():
        _done(3, "Extract", "skipped · all content already processed", 0.0)
        conn.close()
        console.print("\n  [dim]Nothing new since last run.[/dim]")
        return

    num_chunks = math.ceil(len(combined) / CHUNK_SIZE)
    t_step = time.time()
    with console.status(
        f"  [dim]3/5  Extract[/dim]  ~{num_chunks} chunk(s) · calling API...",
        spinner="dots",
    ):
        try:
            raw_triples = extract_triples(
                combined,
                context="Claude Code session and git history for a software project",
            )
        except Exception as e:
            conn.close()
            _err(f"extraction failed: {e}")
    _done(3, "Extract", f"{len(raw_triples)} triples extracted", time.time() - t_step)

    # ── Phase 4: Store + Link ─────────────────────────────────────────────────
    t_step = time.time()
    stored = edges_total = stale_total = 0
    with Progress(
        TextColumn("  [bold]4/5  Store+Link[/bold]"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("", total=len(raw_triples))
        for subj, pred, obj in raw_triples:
            t = Triple(
                subject=subj,
                predicate=pred,
                object=obj,
                session_id=session_id,
                timestamp=datetime.utcnow(),
            )
            _, stale_ids, edges = ingest_triple(conn, t)
            stored += 1
            edges_total += len(edges)
            stale_total += len(stale_ids)
            progress.advance(task)

    # Advance watermarks now that triples are safely stored
    if new_chunks:
        valid_ts = [c["timestamp"] for c in new_chunks if c["timestamp"]]
        if valid_ts:
            set_session_watermark(conn, session_key, max(valid_ts))
    if head_commit and not git_already_processed:
        mark_commit_processed(conn, head_commit)

    conn.close()
    _done(4, "Store+Link", f"{stored} stored · {edges_total} edges · {stale_total} stale", time.time() - t_step)

    # ── Phase 5: Generate ─────────────────────────────────────────────────────
    t_step = time.time()
    with console.status("  [dim]5/5  Generate[/dim]  writing constitution files...", spinner="dots"):
        try:
            written = write_constitution(project)
        except Exception as e:
            _err(f"constitution generation failed: {e}")
    _done(5, "Generate", "CLAUDE.md · .cursorrules · AGENTS.md", time.time() - t_step)

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    mins, secs = divmod(int(elapsed), 60)
    elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"
    console.print(f"\n  [bold]Done in {elapsed_str}[/bold]")
    for path in written.values():
        size = path.stat().st_size
        console.print(f"  [dim]→[/dim] {path}  [dim]{size:,} B[/dim]")


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
