
import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_REDIRECTS = 3
ALLOWED_SCHEMES = {"http", "https"}


def _is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_multicast or not ip.is_global


def _validate_public_preview_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise HTTPException(status_code=400, detail="Unsupported URL scheme")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL host is required")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="URL credentials are not allowed")

    hostname = parsed.hostname.strip().rstrip(".")
    if not hostname:
        raise HTTPException(status_code=400, detail="URL host is required")

    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(hostname, parsed.port)}
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="URL host cannot be resolved") from exc

    if not addresses or any(_is_blocked_ip(address) for address in addresses):
        raise HTTPException(status_code=400, detail="URL host is not allowed")

    return parsed.geturl()


async def _fetch_public_preview(client: httpx.AsyncClient, url: str) -> httpx.Response:
    current_url = _validate_public_preview_url(url)
    for _ in range(MAX_REDIRECTS + 1):
        response = await client.get(current_url, follow_redirects=False)
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                raise HTTPException(status_code=400, detail="Invalid redirect")
            current_url = _validate_public_preview_url(urljoin(current_url, location))
            continue
        return response
    raise HTTPException(status_code=400, detail="Too many redirects")


@router.get("/link-preview", response_model=dict[str, Any])
async def get_link_preview(url: str = Query(..., description="The URL to preview")):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await _fetch_public_preview(client, url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch URL")

            soup = BeautifulSoup(response.text, 'html.parser')

            title = None
            if soup.find("meta", property="og:title"):
                title = soup.find("meta", property="og:title")["content"]
            elif soup.title:
                title = soup.title.string

            description = None
            if soup.find("meta", property="og:description"):
                description = soup.find("meta", property="og:description")["content"]
            elif soup.find("meta", attrs={"name": "description"}):
                description = soup.find("meta", attrs={"name": "description"})["content"]

            image = None
            if soup.find("meta", property="og:image"):
                image = soup.find("meta", property="og:image")["content"]

            return {
                "title": title,
                "description": description,
                "image": image,
                "url": url
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(
            "Error fetching link preview error_type=%s",
            type(e).__name__,
        )
        raise HTTPException(status_code=400, detail="Could not fetch URL") from None
