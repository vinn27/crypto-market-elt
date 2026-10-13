"""Unit tests for the API retry logic in pipelines/extract_load.py.

No network, no Snowflake — the requests layer is faked with mocks, so these
run in CI in under a second and prove the ingestion edge behaviour:
retry-on-429 with backoff, hard-fail after max retries, no retry on 4xx.
"""
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipelines"))

import extract_load as el  # noqa: E402


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self.headers = {"Retry-After": "1"}
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def run_with_responses(responses):
    """Call get_with_retry against a sequence of fake responses; return
    (result_or_exception, number of HTTP calls, number of sleeps)."""
    with mock.patch.object(el.requests, "get", side_effect=responses) as get, \
         mock.patch.object(el.time, "sleep") as sleep:
        try:
            return el.get_with_retry("http://x", {}), get.call_count, sleep.call_count
        except Exception as exc:
            return exc, get.call_count, sleep.call_count


def test_retries_on_429_then_succeeds():
    result, calls, sleeps = run_with_responses(
        [FakeResponse(429), FakeResponse(200, {"prices": [[1, 2]]})]
    )
    assert isinstance(result, dict)          # returned the JSON payload
    assert calls == 2                        # knocked twice
    assert sleeps == 1                       # backed off once


def test_gives_up_after_max_retries():
    result, calls, sleeps = run_with_responses([FakeResponse(429)] * 10)
    assert isinstance(result, RuntimeError)  # surfaced the HTTP error
    assert calls == el.MAX_RETRIES           # exactly the configured tries
    assert sleeps == el.MAX_RETRIES - 1


def test_no_retry_on_client_error():
    result, calls, sleeps = run_with_responses([FakeResponse(404)])
    assert isinstance(result, RuntimeError)
    assert calls == 1                        # 404 is not retryable
    assert sleeps == 0
