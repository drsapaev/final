"""Offsite backup uploader to Cloudflare R2 (S3-compatible, stdlib only).

Design constraints from checkpoint #2772 (medical data):
- Worker credential is bucket-scoped "Object Read & Write" (R2 has no
  write-only tokens); therefore this module NEVER issues Delete/List —
  retention is enforced server-side by owner-managed lifecycle rules.
- Upload happens ONLY for a complete, non-empty, checksummed local file.
- Verification loop is closed locally: PutObject carries
  x-amz-meta-sha256; a follow-up HeadObject must echo back the same
  digest and matching Content-Length before the caller counts the copy
  as offsite-safe.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REQUIRED_VARS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
_SHA_EMPTY = hashlib.sha256(b"").hexdigest()


def r2_configured() -> bool:
    return all(os.getenv(v) for v in _REQUIRED_VARS)


def _env() -> dict[str, str]:
    return {v: (os.getenv(v) or "").strip() for v in (*_REQUIRED_VARS, "R2_BUCKET")}


def _http_request(req: urllib.request.Request, timeout: int = 60):
    """Injection seam for tests."""
    return urllib.request.urlopen(req, timeout=timeout)


def _sign_headers(
    *, account_id: str, access_key: str, secret_key: str,
    method: str, host: str, path: str, body_sha: str,
) -> dict[str, str]:
    t = datetime.now(timezone.utc)
    amz_date = t.strftime("%Y%m%dT%H%M%SZ")
    datestamp = t.strftime("%Y%m%d")
    nl = chr(10)

    header_lines = [
        f"host:{host}",
        f"x-amz-content-sha256:{body_sha}",
        f"x-amz-date:{amz_date}",
    ]
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    if method == "PUT":
        header_lines.append(f"x-amz-meta-sha256:{body_sha}")
        signed_headers += ";x-amz-meta-sha256"

    # Canonical request = METHOD NL URI NL QUERY(empty) NL headers NL NL signedlist NL payload
    canonical_headers = (
        method + nl + path + nl + nl
        + nl.join(header_lines) + nl + nl
        + signed_headers + nl + body_sha
    )
    scope = datestamp + "/auto/s3/aws4_request"
    sts = (
        "AWS4-HMAC-SHA256" + nl + amz_date + nl + scope + nl
        + hashlib.sha256(canonical_headers.encode()).hexdigest()
    )

    def h(key_material_in: bytes, msg: str) -> bytes:
        return hmac.new(key_material_in, msg.encode(), hashlib.sha256).digest()

    key_start = ("AWS4" + secret_key).encode()
    key_material = h(h(h(h(key_start, datestamp), "auto"), "s3"), "aws4_request")
    signature = hmac.new(key_material, sts.encode(), hashlib.sha256).hexdigest()

    headers = {
        "Authorization": (
            "AWS4-HMAC-SHA256 Credential=" + access_key + "/" + scope + ", "
            + "SignedHeaders=" + signed_headers + ", Signature=" + signature
        ),
        "x-amz-content-sha256": body_sha,
        "x-amz-date": amz_date,
    }
    if method == "PUT":
        headers["x-amz-meta-sha256"] = body_sha
    return headers
    return headers


def upload_file(*, key: str, filepath: str | Path) -> dict:
    """PutObject + closed-loop verification. Raises on any mismatch/error.

    Returns dict(key, size, sha256, etag).
    """
    cfg = _env()
    if not all(cfg[v] for v in _REQUIRED_VARS):
        raise RuntimeError(
            "R2 offsite not configured: missing " + ",".join(_REQUIRED_VARS)
        )

    path = Path(filepath)
    if not path.is_file():
        raise ValueError(f"artifact missing: {path}")
    size = path.stat().st_size
    if size == 0:
        # Директива #2772 п.5: никогда не загружать частичный/нулевой файл.
        raise ValueError(f"refusing to upload zero-byte artifact: {path}")

    blob = path.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()

    bucket = cfg["R2_BUCKET"] or "finalclinic-db-backups"
    host = f"{cfg['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    api_path = f"/{bucket}/{key}"

    put_headers = _sign_headers(
        account_id=cfg["R2_ACCOUNT_ID"], access_key=cfg["R2_ACCESS_KEY_ID"],
        secret_key=cfg["R2_SECRET_ACCESS_KEY"], method="PUT", host=host,
        path=api_path, body_sha=sha,
    )
    req = urllib.request.Request(
        f"https://{host}{api_path}", data=blob, method="PUT",
        headers={**put_headers, "Content-Type": "application/gzip"},
    )
    with _http_request(req) as resp:
        etag = resp.headers.get("ETag", "").strip('"')
        resp.read()

    head_headers = _sign_headers(
        account_id=cfg["R2_ACCOUNT_ID"], access_key=cfg["R2_ACCESS_KEY_ID"],
        secret_key=cfg["R2_SECRET_ACCESS_KEY"], method="HEAD", host=host,
        path=api_path, body_sha=_SHA_EMPTY,
    )
    head_req = urllib.request.Request(
        f"https://{host}{api_path}", method="HEAD", headers=head_headers
    )
    with _http_request(head_req) as resp:
        remote_len = int(resp.headers.get("Content-Length", "-1"))
        remote_sha = resp.headers.get("x-amz-meta-sha256", "")

    if remote_len != size or remote_sha != sha:
        raise RuntimeError(
            f"offsite verification mismatch: len {remote_len}!={size}, "
            f"sha {'ok' if remote_sha == sha else 'MISMATCH'}"
        )

    return {"key": key, "size": size, "sha256": sha, "etag": etag}
