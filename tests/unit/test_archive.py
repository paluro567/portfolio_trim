from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from mip.core.exceptions import PermanentError
from mip.ingestion.archive import RawDataArchive

FRAME = pd.DataFrame({"price_date": [date(2026, 6, 1)], "close": [100.0]})


def test_writes_csv_under_category_and_name(tmp_path: Path) -> None:
    archive = RawDataArchive(tmp_path)

    path = archive.write("prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7)

    assert path == tmp_path / "prices" / "AAPL" / "2026-06-01_2026-06-05_run7.csv"
    assert "100.0" in path.read_text()


def test_refuses_overwrite(tmp_path: Path) -> None:
    archive = RawDataArchive(tmp_path)
    archive.write("prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7)

    with pytest.raises(PermanentError, match="refusing to overwrite"):
        archive.write("prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7)


def test_rejected_sidecar_has_distinct_name(tmp_path: Path) -> None:
    archive = RawDataArchive(tmp_path)
    main = archive.write("prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7)
    sidecar = archive.write(
        "prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7, rejected=True
    )

    assert sidecar.name == "2026-06-01_2026-06-05_run7.rejected.csv"
    assert main.exists() and sidecar.exists()
