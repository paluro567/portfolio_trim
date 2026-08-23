"""The historical-provider ingestion contract.

Three things are pinned here, and they are the three that would otherwise be
discovered as a wrong number in a study months later:

* **PIT selection.** A fundamental is selected by FILING date, never by fiscal
  period. Selecting by period silently picks a later restatement.
* **Restated dimensions are inadmissible.** MRQ/MRY/MRT reflect restatements, so
  a record carrying one must never reach the clean layer.
* **Adapter isolation.** No vendor name appears outside the adapter module, and
  the adapter cannot be constructed — let alone fetch — without a key.

No test here requires a subscription, a key, or a network.
"""

from __future__ import annotations

import ast
from datetime import date, datetime
from pathlib import Path

import pytest

from mip.calibration.source import REQUIRED_DATASETS
from mip.core.exceptions import ConfigurationError
from mip.providers.historical.config import (
    HistoricalProviderSettings,
    load_provider_settings,
)
from mip.providers.historical.contract import (
    AS_REPORTED_DIMENSIONS,
    RESTATED_DIMENSIONS,
    HistoricalDataProvider,
    SourceCorporateAction,
    SourceEarningsEvent,
    SourceFundamentalFact,
    blocked_historical_provider,
)
from mip.providers.historical.sharadar import (
    OPTIONAL_TABLES,
    REQUIRED_TABLES,
    TABLE_MAPPINGS,
    SharadarProvider,
    mapping_for,
    unverified_mappings,
)
from mip.providers.historical.staging import STAGES, Stage, stage_spec
from mip.providers.historical.validation import (
    CHECKS,
    checks_for_gate,
    earnings_pit_violations,
    fundamentals_pit_violations,
    select_pit_fundamental,
)


def _fact(dim: str, period: str, filed: str, **kw) -> SourceFundamentalFact:
    return SourceFundamentalFact(
        source_security_id="P123",
        dimension=dim,
        report_period=date.fromisoformat(period),
        filing_date=date.fromisoformat(filed),
        **kw,
    )


# ==========================================================================
# THE CONTRACT REUSES WHAT EXISTS
# ==========================================================================
def test_every_required_logical_dataset_has_a_sharadar_mapping():
    required = {d.name for d in REQUIRED_DATASETS}
    mapped = {m.logical_dataset for m in TABLE_MAPPINGS}
    assert required == mapped, f"unmapped: {required - mapped}"


def test_contract_composes_existing_repository_dtos_rather_than_duplicating():
    """Only the three PIT-specific DTOs are new; the rest are reused."""
    import mip.providers.historical.contract as contract

    source = Path(contract.__file__).read_text()
    assert "from mip.securities.source import" in source
    assert "from mip.research_data.source import" in source
    new_dtos = {"SourceFundamentalFact", "SourceEarningsEvent", "SourceCorporateAction"}
    declared = {
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ClassDef) and node.name.startswith("Source")
    }
    assert declared == new_dtos, f"unexpected new DTOs: {declared - new_dtos}"


def test_provider_protocol_declares_all_eight_loaders():
    for method in (
        "load_security_master",
        "load_universe_membership",
        "load_prices",
        "load_fundamentals_pit",
        "load_sector_history",
        "load_earnings_history",
        "load_corporate_actions",
        "load_delistings",
    ):
        assert hasattr(HistoricalDataProvider, method), method


# ==========================================================================
# PIT SELECTION — THE RULE THAT MATTERS MOST
# ==========================================================================
def test_pit_selection_picks_the_latest_filing_not_the_latest_period():
    """An amended filing that had not yet arrived must not be visible."""
    original = _fact("ARQ", "2020-03-31", "2020-05-01")
    amended = _fact("ARQ", "2020-03-31", "2021-02-01")  # restated a year later

    at_the_time = select_pit_fundamental([original, amended], date(2020, 6, 1))
    assert at_the_time is original, "the later amendment was not knowable in June 2020"

    later = select_pit_fundamental([original, amended], date(2021, 6, 1))
    assert later is amended, "by mid-2021 the amendment had arrived"


def test_pit_selection_excludes_restated_dimensions_entirely():
    restated = _fact("MRQ", "2020-03-31", "2020-05-01")
    assert select_pit_fundamental([restated], date(2024, 1, 1)) is None


def test_pit_selection_returns_none_rather_than_the_nearest_available():
    fact = _fact("ARQ", "2020-03-31", "2020-05-01")
    assert select_pit_fundamental([fact], date(2020, 4, 1)) is None


def test_as_reported_and_restated_dimension_sets_are_disjoint():
    assert AS_REPORTED_DIMENSIONS.isdisjoint(RESTATED_DIMENSIONS)
    assert AS_REPORTED_DIMENSIONS == {"ARQ", "ARY", "ART"}
    assert RESTATED_DIMENSIONS == {"MRQ", "MRY", "MRT"}


def test_is_point_in_time_requires_an_as_reported_dimension():
    assert _fact("ARQ", "2020-03-31", "2020-05-01").is_point_in_time
    assert not _fact("MRQ", "2020-03-31", "2020-05-01").is_point_in_time


def test_fundamentals_violations_flag_future_filings_and_restatements():
    facts = [
        _fact("ARQ", "2020-03-31", "2020-05-01"),  # clean
        _fact("MRQ", "2020-03-31", "2020-05-01"),  # restated
        _fact("ARQ", "2021-03-31", "2021-05-01"),  # not yet filed
        _fact("ARQ", "2020-12-31", "2020-05-01"),  # period after filing: impossible
    ]
    problems = fundamentals_pit_violations(facts, date(2020, 6, 1))
    assert any("restated dimension" in p for p in problems)
    assert any("served at" in p for p in problems)
    assert any("after filing" in p for p in problems)
    assert len(problems) == 3, "the clean fact must not be flagged"


def test_clean_fundamentals_produce_no_violations():
    assert (
        fundamentals_pit_violations([_fact("ARQ", "2020-03-31", "2020-05-01")], date(2020, 6, 1))
        == []
    )


# ==========================================================================
# EARNINGS PIT
# ==========================================================================
def test_earnings_violation_when_observed_after_the_as_of():
    ev = SourceEarningsEvent(
        source_security_id="P1", event_date=date(2020, 1, 1), observed_at=date(2026, 8, 16)
    )
    problems = earnings_pit_violations([ev], date(2020, 6, 1))
    assert any("served at" in p for p in problems)


def test_earnings_violation_when_observed_before_the_event():
    ev = SourceEarningsEvent(
        source_security_id="P1", event_date=date(2020, 6, 1), observed_at=date(2020, 1, 1)
    )
    assert any("before event" in p for p in earnings_pit_violations([ev], date(2021, 1, 1)))


def test_consensus_without_an_observation_date_is_rejected():
    """A consensus figure pulled today is not what the market expected then."""
    ev = SourceEarningsEvent(
        source_security_id="P1",
        event_date=date(2020, 6, 1),
        observed_at=date(2020, 6, 2),
        consensus_eps=1.25,
        consensus_observed_at=None,
    )
    assert not ev.has_contemporaneous_consensus
    assert any("contemporaneous" in p for p in earnings_pit_violations([ev], date(2021, 1, 1)))


def test_contemporaneous_consensus_is_accepted():
    ev = SourceEarningsEvent(
        source_security_id="P1",
        event_date=date(2020, 6, 1),
        observed_at=date(2020, 6, 2),
        announced_at=datetime(2020, 6, 1, 21, 5),
        consensus_eps=1.25,
        consensus_observed_at=date(2020, 5, 28),
    )
    assert ev.has_contemporaneous_consensus
    assert earnings_pit_violations([ev], date(2021, 1, 1)) == []


def test_earnings_event_knowability_is_by_observation_date():
    ev = SourceEarningsEvent(
        source_security_id="P1", event_date=date(2020, 1, 1), observed_at=date(2020, 1, 3)
    )
    assert not ev.knowable_on(date(2020, 1, 2))
    assert ev.knowable_on(date(2020, 1, 3))


# ==========================================================================
# ADAPTER ISOLATION AND SECRETS
# ==========================================================================
def test_vendor_table_codes_appear_only_in_the_adapter_layer():
    """The precise property: no module outside the adapter may name a vendor TABLE.

    Prose mentions of "Sharadar" elsewhere are fine and pre-date this work — the
    securities and research_data modules name candidate vendors in docstrings and
    keep a provider allowlist. What must not leak is a vendor table code, because
    that is what couples code to one supplier.
    """
    allowed = {"sharadar.py", "config.py"}
    offenders = []
    for path in Path("src/mip").rglob("*.py"):
        if path.name in allowed and "providers/historical" in str(path):
            continue
        if "SHARADAR/" in path.read_text():
            offenders.append(str(path))
    assert offenders == [], f"vendor table code leaked: {offenders}"


def test_provider_cannot_be_constructed_without_a_key(monkeypatch):
    monkeypatch.delenv("SHARADAR_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="not configured"):
        SharadarProvider.from_env()


def test_settings_never_serialise_the_secret(monkeypatch):
    monkeypatch.setenv("SHARADAR_API_KEY", "super-secret-value")
    settings = load_provider_settings()
    assert settings.api_key_present
    body = str(settings.to_dict())
    assert "super-secret" not in body
    assert "super-secret" not in repr(settings)


def test_settings_dataclass_has_no_key_field():
    assert "api_key" not in HistoricalProviderSettings.__slots__
    assert "api_key_present" in HistoricalProviderSettings.__slots__


def test_missing_key_is_reported_by_variable_name(monkeypatch):
    monkeypatch.delenv("SHARADAR_API_KEY", raising=False)
    assert "SHARADAR_API_KEY" in (load_provider_settings().blocked_reason() or "")


def test_blocked_provider_raises_on_any_load():
    provider = blocked_historical_provider()
    with pytest.raises(ConfigurationError, match="No survivorship-clean"):
        provider.load_security_master()


def test_adapter_loaders_are_stubs_that_refuse_rather_than_guess():
    """Writing loaders against unverified columns would produce a plausible-looking
    ingestion; the stub says so instead."""
    provider = SharadarProvider(settings=HistoricalProviderSettings("sharadar", True, "x"))
    calls = {
        "load_security_master": (),
        "load_universe_membership": (date(2020, 1, 1),),
        "load_prices": ([], date(2020, 1, 1), date(2020, 2, 1)),
        "load_fundamentals_pit": ([], date(2020, 1, 1)),
        "load_sector_history": ([], date(2020, 1, 1)),
        "load_earnings_history": ([], date(2020, 1, 1)),
        "load_corporate_actions": ([], date(2020, 1, 1), date(2020, 2, 1)),
        "load_delistings": ([],),
    }
    for method, args in calls.items():
        with pytest.raises(NotImplementedError, match="scaffolding"):
            getattr(provider, method)(*args)


# ==========================================================================
# MAPPING HONESTY
# ==========================================================================
def test_unverified_mappings_are_declared_as_such():
    """Field names that could not be confirmed must not masquerade as verified."""
    unverified = {m.logical_dataset for m in unverified_mappings()}
    assert "sector_history" in unverified
    assert "delistings" in unverified
    # The one mapping confirmed from vendor documentation.
    assert mapping_for("fundamentals_pit").verified


def test_fundamentals_mapping_records_the_pit_dimension_rule():
    mapping = mapping_for("fundamentals_pit")
    assert mapping.availability_field == "datekey"
    assert "ARQ" in mapping.limitations and "MRQ" in mapping.limitations


def test_earnings_mapping_records_the_missing_consensus_gap():
    mapping = mapping_for("earnings_history")
    assert "consensus" in mapping.limitations.lower()
    assert "cannot be reconstructed from" in mapping.limitations


def test_delistings_mapping_refuses_to_assume_a_total_loss():
    mapping = mapping_for("delistings")
    assert "UNRESOLVED" in mapping.limitations
    assert "-100%" in mapping.limitations


def test_required_and_optional_tables_are_disjoint():
    assert set(REQUIRED_TABLES).isdisjoint(set(OPTIONAL_TABLES))
    assert "SHARADAR/TICKERS" in REQUIRED_TABLES
    assert "SHARADAR/SP500" in OPTIONAL_TABLES


# ==========================================================================
# STAGING AND QUALITY GATES
# ==========================================================================
def test_stages_run_raw_to_calibration_ready():
    assert [s.stage for s in STAGES] == [
        Stage.RAW,
        Stage.NORMALIZED,
        Stage.PIT_CLEAN,
        Stage.CALIBRATION_READY,
    ]
    for spec in STAGES:
        assert spec.validation and spec.idempotency and spec.lineage and spec.error_handling


def test_pit_clean_stage_is_where_the_as_of_discipline_is_imposed():
    spec = stage_spec(Stage.PIT_CLEAN)
    joined = " ".join(spec.validation).lower()
    assert "never on ticker" in joined
    assert "restated" in joined
    assert "filing date" in joined


def test_quality_checks_map_onto_the_readiness_gate():
    """Every gate check that can be caused by bad ingestion has a DQ check feeding it."""
    for gate_check in (
        "survivorship_control",
        "pit_fundamentals",
        "pit_earnings",
        "pit_classification",
    ):
        assert checks_for_gate(gate_check), f"no DQ check feeds {gate_check}"


def test_the_survivorship_critical_check_exists_and_blocks():
    check = next(c for c in CHECKS if c.name == "delisted_missing_terminal_outcome")
    assert check.severity == "BLOCKING"
    assert check.feeds_gate_check == "survivorship_control"


def test_corporate_action_dto_supports_a_merger_counterparty():
    action = SourceCorporateAction(
        source_security_id="P1",
        ex_date=date(2020, 5, 1),
        action_type="merger",
        contra_source_security_id="P2",
    )
    assert action.contra_source_security_id == "P2"
