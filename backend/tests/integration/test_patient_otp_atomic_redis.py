"""OTP atomicity against Redis, with isolated, disposable keys."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import redis

from app.services.patient_otp_service import _hash_code, _RedisBackend


@pytest.fixture
def redis_otp():
    url = os.getenv("PATIENT_OTP_TEST_REDIS_URL") or os.getenv("ARQ_REDIS_URL")
    if not url:
        if os.getenv("CI"):
            pytest.fail("Redis URL is required for OTP concurrency tests in CI")
        pytest.skip("set PATIENT_OTP_TEST_REDIS_URL to test real Redis")
    client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    client.ping()  # An explicitly configured but unavailable Redis is a failure.
    backend = _RedisBackend.__new__(_RedisBackend)
    backend._client = client
    key = f"test:patient-otp-atomic:{uuid.uuid4().hex}"
    try:
        yield backend, client, key
    finally:
        client.delete(key, f"meta:{key}")
        client.close()


def _parallel(count, action):
    barrier = Barrier(count)

    def run():
        barrier.wait()
        return action()

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(lambda _: run(), range(count)))


def test_redis_correct_code_consumed_once_under_concurrency(redis_otp):
    backend, client, key = redis_otp
    code = _hash_code("123456")
    backend.set(key, code, 60)
    results = _parallel(24, lambda: backend.consume_otp(key, code, 3))
    assert results.count(True) == 1
    assert results.count(False) == 23
    assert client.get(key) is None
    assert client.get(f"meta:{key}") is None


def test_redis_attempt_cap_is_atomic_and_reissue_preserves_it(redis_otp):
    backend, client, key = redis_otp
    code, wrong = _hash_code("123456"), _hash_code("999999")
    backend.set(key, code, 60)
    assert not backend.consume_otp(key, wrong, 3)
    assert 0 < client.ttl(f"meta:{key}") <= 300
    assert _parallel(24, lambda: backend.consume_otp(key, wrong, 3)) == [False] * 24
    assert not backend.consume_otp(key, code, 3)
    assert client.get(key) is None

    client.delete(f"meta:{key}")  # Simulate expiry before the next sequence.
    backend.set(key, code, 60)
    assert not backend.consume_otp(key, wrong, 3)
    assert not backend.consume_otp(key, wrong, 3)
    backend.set(key, _hash_code("654321"), 60)
    assert client.get(f"meta:{key}") is not None
    assert not backend.consume_otp(key, wrong, 3)
    assert not backend.consume_otp(key, _hash_code("654321"), 3)


def test_redis_invalid_metadata_and_missing_expiry_fail_closed(redis_otp):
    backend, client, key = redis_otp
    code = _hash_code("123456")
    backend.set(key, code, 60)
    client.set(f"meta:{key}", "invalid", ex=60)
    assert not backend.consume_otp(key, _hash_code("999999"), 3)
    assert client.get(key) is None

    client.set(key, code)
    assert not backend.consume_otp(key, code, 3)
    assert client.get(key) is None
