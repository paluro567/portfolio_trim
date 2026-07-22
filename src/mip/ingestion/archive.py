"""Immutable raw CSV archive (D5).

Files are written once and never modified. Identity is
`{start}_{end}_run{run_id}[-{label}][.rejected].csv`: the optional label
separates logical passes that cover the same date range within one run
(the price service's within-run full-history refresh uses `full`, so an
incremental rejected artifact and a refresh rejected artifact can never
collide). Re-writing IDENTICAL bytes to an existing path is a logged
no-op — the artifact is already archived; writing DIFFERENT bytes to an
existing path is always a hard error. Overwrites never happen.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from mip.core.exceptions import PermanentError
from mip.core.logging import get_logger

logger = get_logger(__name__)


class RawDataArchive:
    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def write(
        self,
        category: str,  # 'prices' | 'macro' | 'fundamentals' | 'earnings'
        name: str,  # symbol or series code
        frame: pd.DataFrame,
        start: date,
        end: date,
        run_id: int,
        rejected: bool = False,
        label: str = "",
    ) -> Path:
        suffix = ".rejected.csv" if rejected else ".csv"
        qualifier = f"-{label}" if label else ""
        directory = self._root / category / name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{start}_{end}_run{run_id}{qualifier}{suffix}"
        payload = frame.to_csv(index=False)

        if path.exists():
            if path.read_text() == payload:
                logger.info("archive.identical_content_skipped", path=str(path))
                return path
            raise PermanentError(f"archive is immutable — refusing to overwrite {path}")
        try:
            with path.open("x", newline="") as handle:  # 'x': write-once
                handle.write(payload)
        except FileExistsError:
            raise PermanentError(f"archive is immutable — refusing to overwrite {path}") from None

        logger.info("archive.written", path=str(path), rows=len(frame), rejected=rejected)
        return path
