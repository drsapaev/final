#!/usr/bin/env python3
"""Optional isolated DeepSeek bridge for DevBrain LightRAG experiments."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def is_available() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def provider_status() -> str:
    return "deepseek available" if is_available() else "no-key fallback"


def complete(prompt: str, timeout: int = 30) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set; use no-key fallback mode.")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an isolated DevBrain retrieval helper. Do not execute code or access production systems.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek bridge request failed: {exc}") from exc

    return data["choices"][0]["message"]["content"]


def main() -> int:
    print(provider_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
