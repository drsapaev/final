"""Regression coverage for optional SDK startup loading."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_DATABASE_URL = (
    "postgresql+psycopg://test_user:test_password@127.0.0.1:65432/"
    "clinic_bench_import_profile"
)


def _run_import_probe(source: str, *, telegram_token: str = "") -> None:
    """Run one import scenario in a fresh interpreter with synthetic settings."""
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": SYNTHETIC_DATABASE_URL,
            "TESTING": "1",
            "GEMINI_API_KEY": "",
            "TELEGRAM_BOT_TOKEN": telegram_token,
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_gemini_sdk_is_not_imported_with_the_provider_module() -> None:
    _run_import_probe(
        "import sys; import app.services.ai.gemini_provider; "
        "assert 'google.generativeai' not in sys.modules"
    )


def test_configured_telegram_bot_loads_sdk_on_first_access_only() -> None:
    synthetic_token = f"{123456}:{'x' * 35}"
    _run_import_probe(
        "import asyncio\n"
        "import sys\n"
        "from concurrent.futures import ThreadPoolExecutor\n"
        "from app.services.telegram.bot import telegram_bot\n"
        "assert 'aiogram' not in sys.modules\n"
        "with ThreadPoolExecutor(max_workers=2) as executor:\n"
        "    clients = list(executor.map(lambda _: telegram_bot.bot, range(2)))\n"
        "assert clients[0] is clients[1]\n"
        "assert 'aiogram' in sys.modules\n"
        "assert telegram_bot._initialized is True\n"
        "assert telegram_bot.dp is not None\n"
        "asyncio.run(telegram_bot.bot.session.close())",
        telegram_token=synthetic_token,
    )


def test_disabled_telegram_bot_does_not_import_sdk() -> None:
    _run_import_probe(
        "import sys; "
        "from app.services.telegram.bot import telegram_bot; "
        "assert telegram_bot.bot is None; "
        "assert 'aiogram' not in sys.modules"
    )
