"""Preview transport logs cannot contain synthetic fragment capabilities."""

import logging

from app.core.logging_config import protect_telegram_preview_logs, setup_logging


def test_preview_redaction_is_scoped_to_transport_and_restored(capsys):
    root = logging.getLogger()
    transport = logging.getLogger("httpcore.http11")
    other = logging.getLogger("synthetic.application")
    handlers, root_level, transport_level = list(root.handlers), root.level, transport.level
    try:
        setup_logging(level=logging.DEBUG, enable_pii_masking=False)
        transport.setLevel(logging.DEBUG)
        with protect_telegram_preview_logs():
            try:
                raise RuntimeError("#token=SYNTHETIC-SECRET")
            except RuntimeError:
                transport.exception("#token=%s", "SYNTHETIC-SECRET")
            other.warning("unrelated application event")
        transport.warning("unrelated transport event")
        output = capsys.readouterr().out
        assert "SYNTHETIC-SECRET" not in output
        assert "Telegram preview transport event" in output
        assert "unrelated application event" in output
        assert "unrelated transport event" in output
    finally:
        root.handlers[:] = handlers
        root.setLevel(root_level)
        transport.setLevel(transport_level)
