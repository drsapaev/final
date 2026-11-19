"""No credentials, database, Redis or network are needed for these guards."""
import asyncio
import importlib.util
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / "backend/scripts/staging_telegram_reminder.py"
SPEC = importlib.util.spec_from_file_location("staging_telegram_reminder", PATH)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)
CHALLENGE = "a" * 32
NOW = int(time.time())
ISOLATED = {
    "ENV": "staging",
    "DATABASE_URL": "postgresql+psycopg://clinic:fixture@postgres:5432/clinic_staging",
    "ARQ_REDIS_URL": "redis://redis:6379/0",
}
TOKEN = "123456:" + "A" * 30


def update(chat_type="private", sender_id=64, timestamp=NOW, text=None, is_bot=False):
    return {
        "update_id": 1234,
        "message": {
            "chat": {"id": 64, "type": chat_type},
            "from": {"id": sender_id, "is_bot": is_bot},
            "date": timestamp,
            "text": text if text is not None else f"/staging_check {CHALLENGE}",
        },
    }


class TelegramReminderGuards(unittest.TestCase):
    def test_matches_only_one_fresh_private_message(self):
        self.assertEqual(
            check.select_recipient([update()], CHALLENGE, NOW), (64, 1234)
        )
        for batch in (
            [], [update(), update()], [update(chat_type="group")],
            [update(sender_id=65)], [update(timestamp=NOW - 1201)],
            [update(is_bot=True)], [update(text="/start")],
            [update(timestamp=NOW + 1)],
        ):
            with self.subTest(batch=batch), self.assertRaises(check.Refused):
                check.select_recipient(batch, CHALLENGE, NOW)

    def test_wrong_db_and_broker_fail_before_network(self):
        for override in (
            {"ENV": "production"},
            {"DATABASE_URL": "postgresql+psycopg://u:p@postgres:5432/clinic"},
            {"DATABASE_URL": "postgresql+psycopg://u:p@external:5432/clinic_staging"},
            {"ARQ_REDIS_URL": "redis://external:6379/0"},
        ):
            with self.subTest(override=override), patch.dict(
                os.environ, {**ISOLATED, **override}, clear=True
            ), patch.object(check, "api") as api:
                with self.assertRaises(check.Refused):
                    asyncio.run(check.run(TOKEN, CHALLENGE))
                api.assert_not_called()

    def test_wrong_bot_does_not_read_updates_or_send(self):
        with patch.dict(os.environ, ISOLATED, clear=True), patch.object(
            check, "api", return_value={"username": "other_bot", "is_bot": True}
        ) as api:
            with self.assertRaises(check.Refused):
                asyncio.run(check.run(TOKEN, CHALLENGE))
            api.assert_called_once_with(TOKEN, "getMe")

    def test_wrong_chat_fails_before_application_import_or_send(self):
        with patch.dict(os.environ, ISOLATED, clear=True), patch.object(
            check, "api", side_effect=[
                {"username": check.BOT_USERNAME, "is_bot": True},
                [update()], {"id": 999, "type": "private"},
            ],
        ) as api:
            with self.assertRaises(check.Refused):
                asyncio.run(check.run(TOKEN, CHALLENGE))
            self.assertEqual([call.args[1] for call in api.call_args_list],
                             ["getMe", "getUpdates", "getChat"])


if __name__ == "__main__":
    unittest.main()
