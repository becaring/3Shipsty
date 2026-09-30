"""Maintainer-local launcher; fixed paths require this workstation's setup."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(r"D:\Projects\3Shipsty9.x")
PROJECTS = {
    "shipyard": Path(r"D:\Projects\becaring\shipyard"),
    "modern": ROOT / "scratch/deslop-worktree",
    "smash": Path(r"D:\Projects\Smash360\scratch\deslop-worktree"),
    "majora": Path(r"D:\Projects\2Ship3Shipsty"),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PROJECTS:
        raise SystemExit("usage: launch_serena.py shipyard|modern|smash|majora")
    state = ROOT / "scratch/code-nav"
    env = dict(os.environ,
               SERENA_HOME=str(state / "serena-home"),
               UVX=str(state / "venv/Scripts/uvx.exe"),
               UV_CACHE_DIR=str(state / "uv-cache"),
               UV_PYTHON_INSTALL_DIR=str(state / "uv-python"),
               UV_TOOL_DIR=str(state / "uv-tools"),
               UV_OFFLINE="1")
    command = [str(state / "venv/Scripts/serena.exe"), "start-mcp-server",
               "--project", str(PROJECTS[sys.argv[1]]),
               "--enable-web-dashboard", "false", "--open-web-dashboard", "false"]
    raise SystemExit(subprocess.call(command, env=env))


if __name__ == "__main__":
    main()
