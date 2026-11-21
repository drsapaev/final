"""Scoped transport diagnostics must not expose synthetic SMS capabilities."""

import logging

import pytest
from httpcore._trace import Trace

from app.core.logging_config import setup_logging
from app.services.sms_providers import (
    EskizSMSProvider,
    PlayMobileSMSProvider,
    SMSMessage,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["eskiz", "playmobile"])
async def test_sms_trace_is_private_with_explicit_child_debug(
    monkeypatch, capsys, provider_name
):
    from unittest.mock import AsyncMock

    root = logging.getLogger()
    http11 = logging.getLogger("httpcore.http11")
    old_handlers = list(root.handlers)
    old_root_level, old_http11_level = root.level, http11.level
    secret = "SYNTHETIC-TRANSPORT-CAPABILITY"
    phone = "+15550000003"
    body = f"https://example.test/confirm#token={secret}"

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            async with Trace("send_request_body", http11):
                raise RuntimeError(f"echo {phone} {body}")

    try:
        setup_logging(level=logging.DEBUG, enable_pii_masking=False)
        # Explicit child DEBUG bypasses a parent logger level; handler filter
        # still applies to the actual SMS task.
        http11.setLevel(logging.DEBUG)
        monkeypatch.setattr("httpx.AsyncClient", FailingClient)
        if provider_name == "eskiz":
            provider = EskizSMSProvider("synthetic", "synthetic")
            provider._get_auth_token = AsyncMock(return_value="synthetic-auth")
        else:
            provider = PlayMobileSMSProvider("synthetic", "synthetic")
        result = await provider.send_sms(SMSMessage(phone=phone, text=body))
        assert result.success is False
        http11.debug("unrelated httpcore debug remains available")
        http11.warning("transport warning remains available")
        output = capsys.readouterr().out
        assert secret not in output
        assert phone not in output
        assert "#token=" not in output
        assert "unrelated httpcore debug remains available" in output
        assert "transport warning remains available" in output
    finally:
        root.handlers[:] = old_handlers
        root.setLevel(old_root_level)
        http11.setLevel(old_http11_level)


@pytest.mark.asyncio
async def test_sms_filter_is_task_local_during_concurrent_transport(
    monkeypatch, capsys
):
    import asyncio

    root = logging.getLogger()
    http11 = logging.getLogger("httpcore.http11")
    old_handlers = list(root.handlers)
    old_root_level, old_http11_level = root.level, http11.level
    started, release = asyncio.Event(), asyncio.Event()
    secret = "SYNTHETIC-CONCURRENT-CAPABILITY"

    class WaitingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            started.set()
            await release.wait()
            async with Trace("send_request_body", http11):
                raise RuntimeError(f"echo #token={secret}")

    try:
        setup_logging(level=logging.DEBUG, enable_pii_masking=False)
        http11.setLevel(logging.DEBUG)
        monkeypatch.setattr("httpx.AsyncClient", WaitingClient)
        provider = PlayMobileSMSProvider("synthetic", "synthetic")
        task = asyncio.create_task(
            provider.send_sms(SMSMessage(phone="synthetic", text=secret))
        )
        await asyncio.wait_for(started.wait(), timeout=3)
        http11.debug("concurrent non-SMS debug")
        release.set()
        result = await asyncio.wait_for(task, timeout=3)
        assert result.success is False
        output = capsys.readouterr().out
        assert secret not in output
        assert "concurrent non-SMS debug" in output
    finally:
        release.set()
        root.handlers[:] = old_handlers
        root.setLevel(old_root_level)
        http11.setLevel(old_http11_level)
