from __future__ import annotations

import subprocess
from pathlib import Path

from pico_scheduler.src.generator import GeneratorOptions, generate_main_py


def run_git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(
        args, cwd=cwd, text=True, stderr=subprocess.DEVNULL
    ).strip()


def firmware_revision(repo_root: Path, *, git_runner=run_git) -> str:
    try:
        value = git_runner(
            ["git", "log", "-1", "--format=%h", "--", "pico_scheduler/src"],
            repo_root,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return value or "unknown"


def render_scheduler_firmware(repo_root: Path) -> tuple[str, str]:
    revision = firmware_revision(repo_root)
    return revision, generate_main_py(
        firmware_revision=revision,
        options=GeneratorOptions(),
    )
