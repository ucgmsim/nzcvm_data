"""
Command-line interface for managing NZCVM data repository.

This module provides commands for installing and managing the NZCVM data repository,
including cloning from Git, handling Git LFS files, and configuration management.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(pretty_exceptions_enable=False)

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "nzcvm_data"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_ROOT = Path(os.environ.get("NZCVM_DATA_ROOT", Path.home() / ".local" / "cache" / "nzcvm_data_root"))

REPO_URL = "https://github.com/ucgmsim/nzcvm_data.git"


def _save_config(root: Path) -> None:
    """
    Save configuration to config file.

    Parameters
    ----------
    root : Path
        Root directory path to save in configuration.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"data_root": str(root)}, indent=2))


def _load_config() -> Path | None:
    """
    Load configuration from config file.

    Returns
    -------
    Path | None
        Root directory path from configuration, or None if not found/invalid.
    """
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            if path_str := data.get("data_root", ""):
                p = Path(path_str)
                return p if p.exists() else None
        except (json.JSONDecodeError, IOError):
            return None
    return None


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> None:
    """
    Run a subprocess command with logging.

    Parameters
    ----------
    cmd : list[str]
        Command and arguments to run.
    cwd : Path, optional
        Working directory for the command.
    check : bool, optional
        Whether to check return code. Default True.
    """
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=check)


@app.command()
def install(
    path: Annotated[
        Optional[Path],
        typer.Option(
            help="Target directory (default: ~/.local/cache/nzcvm_data_root)"
        ),
    ] = None,
    no_lfs: Annotated[
        bool,
        typer.Option(
            "--no-lfs",
            help="Skip git-lfs (fast: only small files/boundaries)"
        ),
    ] = False,
) -> None:
    """
    Clone/pull the NZCVM LFS repo into a local cache.

    Parameters
    ----------
    path : Path, optional
        Target directory for installation.
    no_lfs : bool, optional
        Skip git-lfs operations.
    """
    root = path if path else DEFAULT_ROOT
    root = root.expanduser().resolve()
    root.parent.mkdir(parents=True, exist_ok=True)

    if root.exists() and any(root.iterdir()):
        print(f"[nzcvm-data] Using existing directory: {root}")
        print("[nzcvm-data] Updating repository...")
        _run(["git", "pull"], cwd=root)
    else:
        print(f"[nzcvm-data] Cloning into: {root}")
        _run(["git", "clone", REPO_URL, str(root)])

    if not no_lfs:
        try:
            _run(["git", "lfs", "install"], cwd=root)
            _run(["git", "lfs", "pull"], cwd=root)
        except subprocess.CalledProcessError:
            print("[nzcvm-data] WARNING: git-lfs failed or is unavailable; large files may remain as pointers.", file=sys.stderr)

    _save_config(root)
    print(f"[nzcvm-data] Config saved at {CONFIG_FILE}")
    print(f"[nzcvm-data] Data root: {root}")


@app.command()
def where() -> None:
    """Print the configured/guessed data root."""
    env = os.environ.get("NZCVM_DATA_ROOT")
    if env and Path(env).expanduser().exists():
        print(Path(env).expanduser().resolve())
        return
    cfg = _load_config()
    if cfg:
        print(cfg)
        return
    print(DEFAULT_ROOT)


if __name__ == "__main__":
    app()
