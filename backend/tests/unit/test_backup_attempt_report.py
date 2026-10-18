"""Scheduled-run diagnostics use only synthetic archives and mocked I/O."""

from __future__ import annotations

import importlib.util
import json
import runpy
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet

from app.services import r2_uploader


@pytest.fixture
def backup(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[3] / "ops/scripts/backup_local_to_r2.py"
    spec = importlib.util.spec_from_file_location("backup_attempt_runner", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    values = {
        "DATABASE_URL": "postgresql://clinic_local_app:SYNTHETIC-NOT-A-SECRET@127.0.0.1:5432/clinic_prod_local",
        "ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "R2_ACCOUNT_ID": "SYNTHETIC-account",
        "R2_ACCESS_KEY_ID": "SYNTHETIC-access",
        "R2_SECRET_ACCESS_KEY": "SYNTHETIC-secret",
    }
    for name in (*r2_uploader._REQUIRED_VARS, "R2_BUCKET"):
        monkeypatch.setenv(name, "SYNTHETIC-placeholder")
    monkeypatch.setattr(runner, "dotenv_values", lambda _: values)

    def fake_subprocess(command, **kwargs):
        assert command[0] in (runner.PG_DUMP, runner.PG_RESTORE)
        return subprocess.CompletedProcess(command, 0, b"PGDMP-SYNTHETIC-archive", b"")

    process = Mock(side_effect=fake_subprocess)
    upload = Mock(return_value={})
    monkeypatch.setattr(runner.subprocess, "run", process)
    monkeypatch.setattr(r2_uploader, "upload_file", upload)
    directory = tmp_path / "backups"
    directory.mkdir()
    argv = [
        "--backup-dir",
        str(directory),
        "--source",
        "local",
        "--schema",
        "public",
        "--offsite-r2",
    ]
    return SimpleNamespace(
        runner=runner, directory=directory, argv=argv, process=process, upload=upload
    )


def read_attempt(backup):
    return json.loads((backup.directory / backup.runner.ATTEMPT_FILENAME).read_text())


def test_success_records_exit_and_running_stage_before_network_call(backup):
    def upload(**kwargs):
        report = read_attempt(backup)
        assert report["state"] == "running"
        assert report["stage"] == "offsite_verification"
        assert report["exit_code"] is None
        assert report["finished_at_utc"] is None

    backup.upload.side_effect = upload
    assert backup.runner.main(backup.argv) == 0
    report = read_attempt(backup)
    assert (report["state"], report["stage"], report["exit_code"]) == (
        "succeeded",
        "completed",
        0,
    )
    assert report["failure_kind"] is None
    assert datetime.fromisoformat(report["started_at_utc"]).tzinfo is not None
    assert datetime.fromisoformat(report["finished_at_utc"]) >= datetime.fromisoformat(
        report["started_at_utc"]
    )
    assert set(report) == {
        "version",
        "run_id",
        "started_at_utc",
        "updated_at_utc",
        "finished_at_utc",
        "state",
        "stage",
        "exit_code",
        "failure_kind",
    }
    assert not list(backup.directory.glob(".backup-attempt-*.tmp"))


def test_dump_failure_is_recorded_without_stderr(backup, capsys):
    private = "SYNTHETIC-private-database-details"
    backup.process.side_effect = None
    backup.process.return_value = subprocess.CompletedProcess(
        [], 1, b"", private.encode()
    )
    assert backup.runner.main(backup.argv) == 1
    report = read_attempt(backup)
    assert (report["state"], report["stage"], report["exit_code"]) == (
        "failed",
        "database_dump",
        1,
    )
    assert private not in json.dumps(report) + capsys.readouterr().out
    backup.upload.assert_not_called()


def test_failed_cloud_upload_preserves_previous_success_manifest(backup):
    assert backup.runner.main(backup.argv) == 0
    manifest = backup.directory / "last_backup_report.json"
    previous_success = manifest.read_bytes()
    backup.upload.side_effect = RuntimeError("SYNTHETIC-private-upload-details")
    assert backup.runner.main(backup.argv) == 1
    report = read_attempt(backup)
    assert report["stage"] == "offsite_verification"
    assert report["state"] == "failed"
    assert manifest.read_bytes() == previous_success


def test_failure_after_verified_upload_identifies_manifest_stage(
    backup, monkeypatch, capsys
):
    original_replace = backup.runner.os.replace
    manifest = backup.directory / "last_backup_report.json"
    previous = '{"SYNTHETIC": "previous-success-record"}'
    manifest.write_text(previous)

    def replace(source, destination):
        if Path(destination).name == "last_backup_report.json":
            raise PermissionError("SYNTHETIC-private-filesystem-details")
        return original_replace(source, destination)

    monkeypatch.setattr(backup.runner.os, "replace", replace)
    assert backup.runner.main(backup.argv) == 1
    backup.upload.assert_called_once()
    report = read_attempt(backup)
    assert (report["stage"], report["exit_code"]) == ("success_manifest", 1)
    assert (
        "SYNTHETIC-private-filesystem-details"
        not in json.dumps(report) + capsys.readouterr().out
    )
    assert manifest.read_text() == previous


@pytest.mark.parametrize("backup_exit", [0, 1])
def test_attempt_io_failure_preserves_backup_exit_and_previous_record(
    backup, monkeypatch, capsys, backup_exit
):
    report_path = backup.directory / backup.runner.ATTEMPT_FILENAME
    previous = '{"version": 1, "state": "previous"}'
    report_path.write_text(previous)
    original_replace = backup.runner.os.replace

    def replace(source, destination):
        if Path(destination).name == backup.runner.ATTEMPT_FILENAME:
            raise PermissionError("SYNTHETIC-private-journal-details")
        return original_replace(source, destination)

    monkeypatch.setattr(backup.runner.os, "replace", replace)
    if backup_exit:
        backup.upload.side_effect = RuntimeError("SYNTHETIC-failure")
    assert backup.runner.main(backup.argv) == backup_exit
    assert report_path.read_text() == previous
    assert not list(backup.directory.glob(".backup-attempt-*.tmp"))
    output = capsys.readouterr().out
    assert output.count("BACKUP ATTEMPT REPORT UNAVAILABLE") == 1
    assert "SYNTHETIC-private-journal-details" not in output


def test_unexpected_failure_has_safe_category_and_last_stage(
    backup, monkeypatch, capsys
):
    def fail(*args, **kwargs):
        raise RuntimeError("SYNTHETIC-private-runtime-details")

    monkeypatch.setattr(backup.runner, "dotenv_values", fail)
    assert backup.runner.main(backup.argv) == 1
    report = read_attempt(backup)
    assert (report["stage"], report["failure_kind"]) == (
        "configuration",
        "unexpected_exception",
    )
    assert (
        "SYNTHETIC-private-runtime-details"
        not in json.dumps(report) + capsys.readouterr().out
    )


def test_interruption_records_exit_130(backup):
    backup.process.side_effect = KeyboardInterrupt
    assert backup.runner.main(backup.argv) == 130
    report = read_attempt(backup)
    assert (report["stage"], report["exit_code"], report["failure_kind"]) == (
        "database_dump",
        130,
        "interrupted",
    )


def test_local_only_success_is_not_cloud_success_evidence(backup):
    assert backup.runner.main(backup.argv[:-1]) == 0
    assert read_attempt(backup)["state"] == "succeeded"
    backup.upload.assert_not_called()
    assert not (backup.directory / "last_backup_report.json").exists()


def test_cli_exit_code_and_preflight_failure_are_recorded(backup, monkeypatch):
    script = Path(backup.runner.__file__)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--backup-dir",
            str(backup.directory),
            "--schema",
            "SYNTHETIC-invalid-schema",
        ],
    )
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(script), run_name="__main__")
    assert stopped.value.code == 1
    report = read_attempt(backup)
    assert (report["stage"], report["state"], report["exit_code"]) == (
        "preflight",
        "failed",
        1,
    )
    backup.process.assert_not_called()
