"""All Merchant API traffic uses a synthetic MockTransport."""
import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from app.core.logging_config import setup_logging
from app.services.click_merchant_status import (
    ClickMerchantStatus,
    ClickMerchantStatusError,
)

ORDER = "invoice_23_11111111-1111-4111-8111-111111111111"
SECRET = "SYNTHETIC_MERCHANT_SECRET"
NOW = 1_800_000_000


def body(value):
    return json.dumps(value).encode()


def transport(first=None, second=None, seen=None):
    first = body({"error_code": 0, "merchant_trans_id": ORDER, "payment_id": 97}) if first is None else first
    second = body({"error_code": 0, "payment_id": "97", "payment_status": 1}) if second is None else second
    calls = [] if seen is None else seen

    def handle(request):
        calls.append(request)
        content = second if len(calls) == 2 else first
        return content if isinstance(content, httpx.Response) else httpx.Response(200, stream=httpx.ByteStream(content))

    return httpx.MockTransport(handle)


@pytest.fixture(autouse=True)
def fake_clock(monkeypatch):
    monkeypatch.setattr("app.services.click_merchant_status.time.time", lambda: NOW)


def client(mock_transport):
    return ClickMerchantStatus(service_id="100", merchant_user_id="200", secret_key=SECRET, transport=mock_transport)


def test_status_observation_binds_order_and_provider_id_without_granting_paid(caplog):
    requests = []
    with caplog.at_level(logging.DEBUG):
        observation = client(transport(seen=requests)).lookup(ORDER)
    assert observation.order_ref == ORDER and observation.provider_payment_id == "97" and observation.status_code == 1
    assert not hasattr(observation, "paid")
    assert len(requests) == 3
    assert all(request.method == "GET" and request.url.scheme == "https" and request.url.host == "api.click.uz" for request in requests)
    assert requests[0].url.path == f"/v2/merchant/payment/status_by_mti/100/{ORDER}"
    assert requests[1].url.path == "/v2/merchant/payment/status/100/97"
    assert requests[2].url.path == requests[0].url.path
    expected = hashlib.sha1((str(NOW) + SECRET).encode(), usedforsecurity=False).hexdigest()
    assert all(request.headers["Auth"] == f"200:{expected}:{NOW}" for request in requests)
    assert SECRET not in caplog.text and expected not in caplog.text
    assert SECRET not in repr(observation)


@pytest.mark.parametrize("invalid", [
    "https://evil.example/steal", "invoice_2_../../attacker", "invoice_1", "invoice_0_11111111-1111-4111-8111-111111111111",
])
def test_arbitrary_order_path_rejected_before_transport(invalid):
    requests = []
    with pytest.raises(ClickMerchantStatusError):
        client(transport(seen=requests)).lookup(invalid)
    assert requests == []


@pytest.mark.parametrize("first,second", [
    (body({"error_code": 0, "merchant_trans_id": "other", "payment_id": 97}), None),
    (body({"error_code": 0, "merchant_trans_id": ORDER, "payment_id": "../path"}), None),
    (body({"error_code": -1, "merchant_trans_id": ORDER, "payment_id": 97}), None),
    (body({"error_code": True, "merchant_trans_id": ORDER, "payment_id": 97}), None),
    (None, body({"error_code": 0, "payment_id": "98", "payment_status": 1})),
    (None, body({"error_code": 0, "payment_id": "97", "payment_status": True})),
    (None, body({"error_code": 0, "payment_id": "97", "payment_status": 1, "status": 2})),
    (None, body({"error_code": 0, "payment_id": "97"})),
    (b'{"error_code":0,"error_code":0}', None),
    (b'{"error_code":NaN}', None),
    (b'x' * 65537, None),
    (httpx.Response(302, headers={"location": "https://evil.example/steal"}), None),
    (httpx.Response(200, headers={"content-encoding": "gzip"}, stream=httpx.ByteStream(b'{}')), None),
])
def test_incomplete_ambiguous_or_redirected_results_fail_closed(first, second):
    with pytest.raises(ClickMerchantStatusError):
        client(transport(first, second)).lookup(ORDER)


@pytest.mark.parametrize("bad", ["", "0", "../100", "100\nheader", "100.0"])
def test_untrusted_service_or_user_identifier_cannot_change_destination(bad):
    with pytest.raises(ClickMerchantStatusError):
        ClickMerchantStatus(service_id=bad, merchant_user_id="200", secret_key=SECRET)
    with pytest.raises(ClickMerchantStatusError):
        ClickMerchantStatus(service_id="100", merchant_user_id=bad, secret_key=SECRET)


def test_transport_timeout_is_sanitized():
    def fail(request):
        raise httpx.ConnectTimeout("SYNTHETIC_MERCHANT_SECRET")

    with pytest.raises(ClickMerchantStatusError) as raised:
        client(httpx.MockTransport(fail)).lookup(ORDER)
    assert SECRET not in str(raised.value)


def test_order_remap_during_status_lookup_requires_reconciliation():
    count = 0

    def remapping(request):
        nonlocal count
        count += 1
        if count == 2:
            payload = {"error_code": 0, "payment_id": "97", "status": 1}
        else:
            payload = {"error_code": 0, "merchant_trans_id": ORDER, "payment_id": 97 if count == 1 else 98}
        return httpx.Response(200, stream=httpx.ByteStream(body(payload)))

    with pytest.raises(ClickMerchantStatusError, match="order changed"):
        client(httpx.MockTransport(remapping)).lookup(ORDER)


@pytest.mark.parametrize("structured", [False, True])
def test_application_handler_redacts_only_active_click_transport(capsys, structured):
    root = logging.getLogger()
    names = ("httpx", "httpcore.http11", "uvicorn", "uvicorn.access", "fastapi")
    levels = {name: logging.getLogger(name).level for name in names}
    old_handlers, old_level = list(root.handlers), root.level
    barrier = threading.Barrier(2)
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            barrier.wait(timeout=5)
            logging.getLogger("httpcore.http11").debug("request %s auth %s", ORDER, request.headers["Auth"], extra={"request_id": ORDER})
            try:
                raise ValueError(SECRET)
            except ValueError:
                logging.getLogger("httpcore.http11").exception("exception with %s", ORDER)
        payload = ({"error_code": 0, "merchant_trans_id": ORDER, "payment_id": 97}
                   if calls != 2 else {"error_code": 0, "payment_id": 97, "status": 1})
        return httpx.Response(200, stream=httpx.ByteStream(body(payload)))

    def unrelated():
        barrier.wait(timeout=5)
        logging.getLogger("httpx").info("UNRELATED-HTTP-DIAGNOSTIC")

    try:
        setup_logging(level=logging.DEBUG, enable_pii_masking=False, structured=structured)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(unrelated)
            client(httpx.MockTransport(handle)).lookup(ORDER)
            future.result(timeout=5)
        logging.getLogger("httpx").info("AFTER-CLICK-DIAGNOSTIC")
        output = capsys.readouterr().out
        assert "Click provider transport event" in output
        assert "UNRELATED-HTTP-DIAGNOSTIC" in output and "AFTER-CLICK-DIAGNOSTIC" in output
        assert ORDER not in output and SECRET not in output
    finally:
        root.handlers[:] = old_handlers
        root.setLevel(old_level)
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)


def test_click_log_scope_is_restored_after_cancellation(capsys):
    root = logging.getLogger()
    names = ("httpx", "httpcore.http11", "uvicorn", "uvicorn.access", "fastapi")
    levels = {name: logging.getLogger(name).level for name in names}
    old_handlers, old_level = list(root.handlers), root.level

    def cancelled(request):
        logging.getLogger("httpx").error("private %s", ORDER)
        raise KeyboardInterrupt()

    try:
        setup_logging(level=logging.DEBUG, enable_pii_masking=False)
        with pytest.raises(KeyboardInterrupt):
            client(httpx.MockTransport(cancelled)).lookup(ORDER)
        logging.getLogger("httpx").info("AFTER-CANCELLATION")
        output = capsys.readouterr().out
        assert ORDER not in output and "AFTER-CANCELLATION" in output
    finally:
        root.handlers[:] = old_handlers
        root.setLevel(old_level)
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)
