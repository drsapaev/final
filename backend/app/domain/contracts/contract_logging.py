from __future__ import annotations

import logging
from typing import Any


class ContractMethodLogger:
    """Small helper for consistent contract-level debug logs."""

    def __init__(self, logger: logging.Logger, namespace: str) -> None:
        self._logger = logger
        self._namespace = namespace

    def log_entry(self, method: str, request_id: str | None, **details: Any) -> None:
        self._logger.debug(
            "contract.%s.%s.entry request_id=%s %s",
            self._namespace,
            method,
            request_id or "-",
            _format_details(details),
        )

    def log_exit(self, method: str, request_id: str | None, **details: Any) -> None:
        self._logger.debug(
            "contract.%s.%s.exit request_id=%s %s",
            self._namespace,
            method,
            request_id or "-",
            _format_details(details),
        )


def _format_details(details: dict[str, Any]) -> str:
    if not details:
        return ""
    return " ".join(f"{key}={value!r}" for key, value in details.items())

