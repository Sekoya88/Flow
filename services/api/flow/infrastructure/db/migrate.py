from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_migrations() -> None:
    alembic_dir = Path(__file__).parent.parent.parent.parent  # services/api root
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=alembic_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or "(no output)"
        raise RuntimeError(
            f"Alembic migration failed (exit {result.returncode}):\n{msg}"
        )
