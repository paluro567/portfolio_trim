"""Stable "latest report" store.

`<report_root>/latest/` always holds the most recent successfully
generated report of each kind under a fixed, untimestamped name:

    Portfolio.{txt,md,json}     portfolio decision report
    <SYMBOL>.{md,json}          institutional research report
    <SYMBOL>_decision.{txt,md,json}  single-symbol decision report

Dated historical report directories are a separate concern and are never
touched here. Replacement is atomic: content is fully written and fsynced
to a temp file in the destination directory, then `os.replace`d over the
target — so a failure at any point leaves the previous latest file
exactly as it was, with no partial content and no leftover temp file.
"""

import os
import tempfile
from pathlib import Path

LATEST_DIRNAME = "latest"


def latest_dir(report_root: Path | str) -> Path:
    return Path(report_root) / LATEST_DIRNAME


def publish_latest(report_root: Path | str, filename: str, content: str) -> Path:
    """Atomically overwrite `<report_root>/latest/<filename>`.

    A trailing newline is appended if missing, so latest files match what
    the CLI printed to the terminal. Returns the final path."""
    directory = latest_dir(report_root)
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / filename
    if not content.endswith("\n"):
        content += "\n"
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=directory,
        prefix=f".{final.stem}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, final)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
    return final
