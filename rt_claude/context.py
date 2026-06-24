import subprocess
from pathlib import Path
from typing import Optional

def resolve_context(cwd: str) -> dict:
    project = _git_repo_name(cwd) or Path(cwd).name
    return {"project": project, "branch": _git_branch(cwd)}

def _git_branch(cwd) -> Optional[str]:
    out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return out or None

def _git_repo_name(cwd) -> Optional[str]:
    top = _run(["git", "rev-parse", "--show-toplevel"], cwd)
    return Path(top).name if top else None

def _run(args, cwd) -> Optional[str]:
    try:
        res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            return res.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None
