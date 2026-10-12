"""Tests for retry engine."""

import pytest

from reroute.retry.retry import RetryEngine


@pytest.mark.asyncio
async def test_success_no_retry():
    engine = RetryEngine()
    call_count = 0

    async def ok():
        nonlocal call_count
        call_count += 1
        return "done"

    result = await engine.execute(ok)
    assert result == "done"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retries_on_timeout():
    engine = RetryEngine()
    engine.max_attempts = 2
    call_count = 0

    import httpx

    async def fail_then_ok():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.TimeoutException("timeout")
        return "ok"

    result = await engine.execute(fail_then_ok)
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_does_not_retry_non_retryable():
    engine = RetryEngine()
    engine.max_attempts = 3

    async def always_fail():
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        await engine.execute(always_fail)


@pytest.mark.asyncio
async def test_retry_records_metric_with_labels():
    from unittest.mock import patch

    import httpx

    engine = RetryEngine()
    engine.max_attempts = 2
    engine.base_delay = 0.0
    call_count = 0

    async def fail_then_ok():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.TimeoutException("timeout")
        return "ok"

    with patch("reroute.retry.retry.metrics_collector") as mc:
        result = await engine.execute(fail_then_ok, labels=("openai", "gpt-4o"))

    assert result == "ok"
    mc.record_retry.assert_called_once_with("openai", "gpt-4o")
