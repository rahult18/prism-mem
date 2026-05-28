import click


@click.group()
def cli():
    """Prism — post-session knowledge crystallizer for AI coding agents."""


@cli.command()
@click.option("--project", default=".", show_default=True, help="Path to the project root.")
@click.option("--session", default=None, help="Specific session ID to process (default: most recent).")
def crystallize(project, session):
    """Read the last session + git history, extract triples, regenerate constitution files."""
    click.echo("not implemented yet")


@cli.command()
def serve():
    """Start the MCP server (stdio mode)."""
    click.echo("not implemented yet")


@cli.command()
def ui():
    """Start the graph UI at http://localhost:7823."""
    click.echo("not implemented yet")


@cli.group()
def hook():
    """Manage the git post-commit hook."""


@hook.command("install")
@click.option("--project", default=".", show_default=True, help="Path to the project root.")
def hook_install(project):
    """Install the post-commit hook in the given project."""
    click.echo("not implemented yet")


@hook.command("uninstall")
@click.option("--project", default=".", show_default=True, help="Path to the project root.")
def hook_uninstall(project):
    """Remove the post-commit hook from the given project."""
    click.echo("not implemented yet")
