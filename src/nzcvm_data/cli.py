import os
import sys
import json
import subprocess
from pathlib import Path
import argparse

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "nzcvm_data"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_ROOT = Path(os.environ.get("NZCVM_DATA_ROOT", Path.home() / ".local" / "cache" / "nzcvm_data_root"))

REPO_URL = "https://github.com/ucgmsim/nzcvm_data.git"

def _save_config(root: Path):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"data_root": str(root)}, indent=2))

def _load_config() -> Path | None:
    if CONFIG_FILE.exists():
        try:
            p = Path(json.loads(CONFIG_FILE.read_text()).get("data_root", ""))
            return p if p.exists() else None
        except Exception:
            return None
    return None

def _run(cmd, cwd=None, check=True):
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=check)

def cmd_install(args):
    root = Path(args.path) if args.path else DEFAULT_ROOT
    root = root.expanduser().resolve()
    root.parent.mkdir(parents=True, exist_ok=True)

    if root.exists() and any(root.iterdir()):
        print(f"[nzcvm-data] Using existing directory: {root}")
    else:
        print(f"[nzcvm-data] Cloning into: {root}")
        _run(["git", "clone", REPO_URL, str(root)])

    if not args.no_lfs:
        try:
            _run(["git", "lfs", "install"], cwd=root)
            _run(["git", "lfs", "pull"], cwd=root)
        except subprocess.CalledProcessError:
            print("[nzcvm-data] WARNING: git-lfs failed or is unavailable; large files may remain as pointers.", file=sys.stderr)

    _save_config(root)
    print(f"[nzcvm-data] Config saved at {CONFIG_FILE}")
    print(f"[nzcvm-data] Data root: {root}")

def cmd_where(_args):
    env = os.environ.get("NZCVM_DATA_ROOT")
    if env and Path(env).expanduser().exists():
        print(Path(env).expanduser().resolve()); return
    cfg = _load_config()
    if cfg:
        print(cfg); return
    print(DEFAULT_ROOT)

def app():
    p = argparse.ArgumentParser(prog="nzcvm-data", description="NZCVM data manager")
    sub = p.add_subparsers(dest="cmd")

    i = sub.add_parser("install", help="Clone/pull the NZCVM LFS repo into a local cache.")
    i.add_argument("--path", type=str, help="Target directory (default: ~/.local/cache/nzcvm_data_root)")
    i.add_argument("--no-lfs", action="store_true", help="Skip git-lfs (fast: only small files/boundaries).")
    i.set_defaults(func=cmd_install)

    w = sub.add_parser("where", help="Print the configured/guessed data root.")
    w.set_defaults(func=cmd_where)

    args = p.parse_args()
    if not args.cmd:
        p.print_help(); sys.exit(1)
    args.func(args)

