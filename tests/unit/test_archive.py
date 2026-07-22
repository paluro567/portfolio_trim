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


def test_refuses_overwrite_with_different_content(tmp_path: Path) -> None:
    archive = RawDataArchive(tmp_path)
    archive.write("prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7)

    changed = FRAME.assign(close=[999.0])
    with pytest.raises(PermanentError, match="refusing to overwrite"):
        archive.write("prices", "AAPL", changed, date(2026, 6, 1), date(2026, 6, 5), run_id=7)


def test_identical_content_is_deduplicated_not_overwritten(tmp_path: Path) -> None:
    archive = RawDataArchive(tmp_path)
    first = archive.write("prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7)
    before = first.read_text()

    again = archive.write("prices", "AAPL", FRAME.copy(), date(2026, 6, 1), date(2026, 6, 5), 7)

    assert again == first and first.read_text() == before  # one artifact, untouched
    assert len(list(first.parent.iterdir())) == 1


def test_label_gives_passes_distinct_identities(tmp_path: Path) -> None:
    archive = RawDataArchive(tmp_path)
    incremental = archive.write(
        "prices", "SNOW", FRAME, date(2026, 7, 20), date(2026, 7, 20), run_id=45, rejected=True
    )
    changed = FRAME.assign(close=[111.0])
    full = archive.write(
        "prices",
        "SNOW",
        changed,
        date(2026, 7, 20),
        date(2026, 7, 20),
        run_id=45,
        rejected=True,
        label="full",
    )

    assert incremental.name == "2026-07-20_2026-07-20_run45.rejected.csv"
    assert full.name == "2026-07-20_2026-07-20_run45-full.rejected.csv"
    assert incremental.exists() and full.exists()  # neither pass lost data


def test_rejected_sidecar_has_distinct_name(tmp_path: Path) -> None:
    archive = RawDataArchive(tmp_path)
    main = archive.write("prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7)
    sidecar = archive.write(
        "prices", "AAPL", FRAME, date(2026, 6, 1), date(2026, 6, 5), run_id=7, rejected=True
    )

    assert sidecar.name == "2026-06-01_2026-06-05_run7.rejected.csv"
    assert main.exists() and sidecar.exists()
