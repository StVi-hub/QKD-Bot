"""Metadata stored with every result: which code, which environment, which seed."""

import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy
import qiskit
import qiskit_aer

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_PATHS = ["src", "scripts", "pyproject.toml"]  # everything that can change a result


def _git(*args):
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def provenance(seed, n):
    """JSON-ready metadata. git_dirty = True means the code differs from git_commit, so the
    result cannot be reproduced from that commit alone."""
    status = _git("status", "--porcelain", "--", *CODE_PATHS)
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": None if status is None else bool(status),
        "python": platform.python_version(),
        "qiskit": qiskit.__version__,
        "qiskit_aer": qiskit_aer.__version__,
        "numpy": numpy.__version__,
        "platform": platform.platform(),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "n": n,
    }
