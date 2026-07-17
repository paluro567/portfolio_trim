"""Decision engine layer (architecture-reserved): the Decision Evidence
Engine (combined descriptive evidence), the Trim Score Engine (the
transparent transformation of that evidence into horizon-specific trim
assessments), and the Evidence Attribution Engine (the exact accounting
of every trim score)."""

from mip.engine.attribution import (
    AttributionEngine,
    AttributionReport,
    EvidenceContribution,
    attribute,
)
from mip.engine.evidence import (
    DecisionEvidence,
    DecisionEvidenceEngine,
    ModelContribution,
    combine_model_evidence,
)
from mip.engine.report import (
    PortfolioDecisionReport,
    ReportGenerator,
    ReportOptions,
    SymbolDecisionReport,
    build_portfolio_report,
    build_symbol_report,
)
from mip.engine.trim import (
    LabelBand,
    TrimAssessment,
    TrimConfig,
    TrimScoreEngine,
    assess_symbol,
    assess_trim,
)

__all__ = [
    "AttributionEngine",
    "AttributionReport",
    "DecisionEvidence",
    "DecisionEvidenceEngine",
    "EvidenceContribution",
    "LabelBand",
    "PortfolioDecisionReport",
    "ReportGenerator",
    "ReportOptions",
    "SymbolDecisionReport",
    "ModelContribution",
    "TrimAssessment",
    "TrimConfig",
    "TrimScoreEngine",
    "assess_symbol",
    "assess_trim",
    "attribute",
    "build_portfolio_report",
    "build_symbol_report",
    "combine_model_evidence",
]
