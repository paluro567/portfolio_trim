"""Platform exception hierarchy.

Later phases extend this; Phase 0 defines only what core infrastructure
needs. The transient/permanent split is the contract the retry decorator
relies on: transient errors are retried, permanent errors are not.
"""


class MIPError(Exception):
    """Base class for all platform errors."""


class ConfigurationError(MIPError):
    """Settings are missing or invalid. Raised at startup, never mid-run."""


class TransientError(MIPError):
    """A retryable failure (network hiccup, rate limit, timeout)."""


class PermanentError(MIPError):
    """A non-retryable failure (bad symbol, auth failure, contract violation)."""
