import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def read_git_diff(project_path: str) -> str:
    path = str(Path(project_path).resolve())
    return _run_git(["diff", "HEAD~1", "HEAD"], cwd=path)


def read_git_log(project_path: str, n: int = 20) -> str:
    path = str(Path(project_path).resolve())
    return _run_git(["log", "--oneline", f"-{n}"], cwd=path)


def read_git_head(project_path: str) -> str:
    """Return the current HEAD commit hash, or empty string if no commits."""
    path = str(Path(project_path).resolve())
    return _run_git(["rev-parse", "HEAD"], cwd=path)


if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "."

    print("=== GIT LOG ===")
    log = read_git_log(project)
    print(log or "(no commits)")

    print("\n=== GIT DIFF (HEAD~1..HEAD) ===")
    diff = read_git_diff(project)
    print(diff or "(no diff — possibly only one commit or no commits)")
