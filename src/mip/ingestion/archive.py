"""Immutable raw CSV archive (D5).

Files are written once and never modified: the writer opens with mode 'x'
and raises on any existing path. Rejected (quarantined) rows get a
.rejected.csv sidecar next to the main file.
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
    ) -> Path:
        suffix = ".rejected.csv" if rejected else ".csv"
        directory = self._root / category / name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{start}_{end}_run{run_id}{suffix}"

        try:
            with path.open("x", newline="") as handle:  # 'x': write-once
                frame.to_csv(handle, index=False)
        except FileExistsError:
            raise PermanentError(f"archive is immutable — refusing to overwrite {path}") from None

        logger.info("archive.written", path=str(path), rows=len(frame), rejected=rejected)
        return path
