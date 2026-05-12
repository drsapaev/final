"""
Helpers for validating user-configured outbound URLs.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_PUBLIC_HTTP_SCHEMES = {"http", "https"}


def _is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_multicast or not ip.is_global


def validate_public_http_url(raw_url: str) -> str:
    """Return a normalized public HTTP(S) URL or raise ValueError."""
    parsed = urlparse(str(raw_url))
    if parsed.scheme.lower() not in ALLOWED_PUBLIC_HTTP_SCHEMES:
        raise ValueError("URL scheme must be http or https")
    if not parsed.hostname:
        raise ValueError("URL host is required")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not allowed")

    hostname = parsed.hostname.strip().rstrip(".")
    if not hostname:
        raise ValueError("URL host is required")

    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(hostname, parsed.port)}
    except socket.gaierror as exc:
        raise ValueError("URL host cannot be resolved") from exc

    if not addresses or any(_is_blocked_ip(address) for address in addresses):
        raise ValueError("URL host is not allowed")

    return parsed.geturl()
