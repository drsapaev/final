#!/usr/bin/env python3
"""Round-15 acceptance tests (PR-6 #3215, owner codex review P1 — ReDoS).

The review's acceptance criteria:
  1. a LONG percent-encoded input WITHOUT a credential field must be
     processed in bounded time through the REAL RequestValidationError
     handler (the handler is shared by every endpoint — e.g. login —
     so the path is reachable pre-auth and independent of FCM);
  2. the event loop must stay RESPONSIVE while the 422 is produced
     (the old code ran a quadratic regex synchronously inside the
     async handler and starved every other task);
  3. the response must still be the expected 422 with a bounded
     "input" echo.

The tests build a minimal FastAPI app and register the PRODUCTION
exception handlers (app.core.exception_handlers.register_exception_handlers)
— no database, no auth, the exact handler code path.
"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from app.core.exception_handlers import (  # noqa: E402
    _VALIDATION_INPUT_PREVIEW_LEN,
    register_exception_handlers,
)


class _ProbeModel(BaseModel):
    """Any typed body model: a wrong-typed huge string reaches
    _sanitize_validation_errors → mask_pii → the fixed scan path."""

    code: int


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/probe")
    async def probe(payload: _ProbeModel) -> dict:  # pragma: no cover
        return {"ok": True}

    return app


def _poc_body(n: int) -> dict:
    """The review's PoC payload delivered as a wrong-typed JSON field:
    the full string lands in error["input"] unbounded (round-9 path)."""
    return {"code": "x=" + "%61" * n}


@pytest.mark.asyncio
async def test_422_on_huge_credential_free_body_is_fast_and_loop_stays_responsive():
    """Bounded 422 latency + concurrent ticker keeps ticking throughout."""
    app = _build_app()
    tick_gaps: list[float] = []
    stop = asyncio.Event()

    async def _ticker() -> None:
        last = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(0.001)
            now = time.perf_counter()
            tick_gaps.append(now - last)
            last = now

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ticker_task = asyncio.create_task(_ticker())
        # Let the ticker establish a baseline heartbeat BEFORE the request,
        # so any mid-request stall shows up as a huge inter-tick gap.
        await asyncio.sleep(0.002)
        try:
            start = time.perf_counter()
            resp = await client.post("/probe", json=_poc_body(16000))  # 48 KB
            elapsed = time.perf_counter() - start
        finally:
            stop.set()
            await ticker_task

    # 1. expected 422
    assert resp.status_code == 422

    # 2. bounded processing time (was 5.35 s pre-fix at this size)
    assert elapsed < 1.0, f"422 took {elapsed:.3f}s — ReDoS regression"

    # 3. event loop responsiveness: the ticker established a heartbeat
    # before the request; if the handler had stalled the loop (the old
    # quadratic regex), the next tick would only fire after the stall —
    # a multi-second gap. (A yield-free fast request legitimately adds
    # no new ticks — hence default=0, the stall signal is a LARGE gap,
    # not the tick count.)
    assert tick_gaps, "ticker heartbeat missing — baseline was not established"
    assert max(tick_gaps) < 1.0, (
        f"event loop stalled for {max(tick_gaps):.3f}s during 422 handling"
    )


@pytest.mark.asyncio
async def test_422_response_echoes_bounded_sanitized_input():
    """The 422 detail must keep the round-9/10 contract: sanitized and
    truncated to _VALIDATION_INPUT_PREVIEW_LEN — never the raw payload."""
    app = _build_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/probe", json=_poc_body(16000))

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    inputs = [e.get("input") for e in detail if isinstance(e, dict)]
    assert inputs, "validation error carried no input echo"
    for value in inputs:
        assert isinstance(value, str)
        # Credential-FREE payloads echo only as a bounded preview.
        assert len(value) <= _VALIDATION_INPUT_PREVIEW_LEN + len("...[TRUNCATED]")


@pytest.mark.asyncio
async def test_422_echo_redacts_credential_shaped_input():
    """The leak half of the round-9/10 contract: a credential-bearing
    input must never echo its secret into the 422 detail."""
    app = _build_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/probe", json={"code": "token=pr6-secret-credential-value"}
        )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    echoed = str(detail)
    assert "pr6-secret-credential-value" not in echoed
    assert "token=[REDACTED]" in echoed


@pytest.mark.asyncio
async def test_422_on_oversized_percent_body_from_login_shaped_model():
    """A second, differently-shaped hostile body (percent-heavy, no
    credential field, no JSON structure at all — raw bytes path)."""
    app = _build_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Unterminated JSON of 64 KB: RequestValidationError carries the
        # raw body bytes → bytes-decode path (round 10) → mask_pii.
        raw = b'{"code": "' + b"a" * 64000
        start = time.perf_counter()
        resp = await client.post(
            "/probe", content=raw, headers={"content-type": "application/json"}
        )
        elapsed = time.perf_counter() - start

    assert resp.status_code == 422
    assert elapsed < 1.0, f"422 took {elapsed:.3f}s — ReDoS regression"
