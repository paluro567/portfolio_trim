import pytest

from mip.core.exceptions import PermanentError, TransientError
from mip.core.retry import retry


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def test_transient_error_retried_until_success() -> None:
    sleeper = SleepRecorder()
    calls = {"n": 0}

    @retry(max_attempts=4, backoff_seconds=1.0, sleep=sleeper)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("rate limited")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3
    assert sleeper.delays == [1.0, 2.0]  # exponential backoff


def test_gives_up_after_max_attempts_and_raises_last_error() -> None:
    sleeper = SleepRecorder()
    calls = {"n": 0}

    @retry(max_attempts=3, backoff_seconds=0.5, sleep=sleeper)
    def always_failing() -> None:
        calls["n"] += 1
        raise TransientError(f"failure {calls['n']}")

    with pytest.raises(TransientError, match="failure 3"):
        always_failing()
    assert calls["n"] == 3
    assert sleeper.delays == [0.5, 1.0]  # no sleep after the final attempt


def test_permanent_error_not_retried() -> None:
    sleeper = SleepRecorder()
    calls = {"n": 0}

    @retry(max_attempts=5, sleep=sleeper)
    def broken() -> None:
        calls["n"] += 1
        raise PermanentError("bad symbol")

    with pytest.raises(PermanentError):
        broken()
    assert calls["n"] == 1
    assert sleeper.delays == []


def test_unrelated_exception_not_retried() -> None:
    calls = {"n": 0}

    @retry(max_attempts=5, sleep=SleepRecorder())
    def buggy() -> None:
        calls["n"] += 1
        raise ValueError("a bug, not a network issue")

    with pytest.raises(ValueError):
        buggy()
    assert calls["n"] == 1


def test_custom_retry_on_types() -> None:
    sleeper = SleepRecorder()
    calls = {"n": 0}

    @retry(max_attempts=2, backoff_seconds=0.1, retry_on=(ConnectionError,), sleep=sleeper)
    def net_flaky() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("reset")
        return "ok"

    assert net_flaky() == "ok"
    assert sleeper.delays == [0.1]


def test_max_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        retry(max_attempts=0)
