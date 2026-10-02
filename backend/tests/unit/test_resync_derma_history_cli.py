from __future__ import annotations

"""CLI resync_derma_history.py (P2-1, owner fact-check 5625c8f1b).

Прежний ручной парсер понимал только «--database-url=...» —
задокументированные формы «--database-url <url>» и позиционный «<url>»
молча игнорировались, и при выставленном DATABASE_URL окружения
пересчёт тихо шёл в окружение: DELETE всей таблицы по STAGING при
переданном аргументом PROD с сообщением об успехе. Теперь argparse +
печать цели перед стартом (хост/БД/режим, пароль замаскирован).
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "resync_derma_history.py"
)


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "resync_derma_history_cli", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


class TestResyncDermaHistoryCliArgs:
    def test_space_form_flag_wins_over_env(self):
        """Репро владельца: --database-url <url> (через пробел) при
        выставленном DATABASE_URL — побеждает аргумент, не окружение."""
        args = cli.build_parser().parse_args(["--database-url", "sqlite:///flag.db"])
        assert args.database_url == "sqlite:///flag.db"
        assert (
            cli.resolve_database_url(args, {"DATABASE_URL": "sqlite:///env.db"})
            == "sqlite:///flag.db"
        )

    def test_equals_form_flag(self):
        args = cli.build_parser().parse_args(["--database-url=sqlite:///eq.db"])
        assert cli.resolve_database_url(args, {}) == "sqlite:///eq.db"

    def test_positional_url_form(self):
        """Вторая задокументированная форма — позиционный url."""
        args = cli.build_parser().parse_args(["sqlite:///positional.db"])
        assert args.url == "sqlite:///positional.db"
        assert cli.resolve_database_url(args, {}) == "sqlite:///positional.db"

    def test_env_fallback_only_without_explicit_args(self):
        args = cli.build_parser().parse_args([])
        assert (
            cli.resolve_database_url(args, {"DATABASE_URL": "sqlite:///env.db"})
            == "sqlite:///env.db"
        )

    def test_missing_url_refuses(self):
        args = cli.build_parser().parse_args([])
        with pytest.raises(SystemExit):
            cli.resolve_database_url(args, {})

    def test_flag_and_positional_conflict_refuses(self):
        args = cli.build_parser().parse_args(["--database-url", "a", "b"])
        with pytest.raises(SystemExit):
            cli.resolve_database_url(args, {})

    def test_visit_ids_parsing(self):
        assert cli.parse_visit_ids(None) is None
        assert cli.parse_visit_ids("12,34") == [12, 34]
        assert cli.parse_visit_ids(" 7 ") == [7]
        with pytest.raises(SystemExit):
            cli.parse_visit_ids("12,,34")
        with pytest.raises(SystemExit):
            cli.parse_visit_ids("12,")
        with pytest.raises(SystemExit):
            cli.parse_visit_ids("abc")

    def test_describe_target_masks_password_and_names_target(self):
        # CodeQL (py/incomplete-url-substring-sanitization): точное
        # равенство вместо substring-проверок по URL-производной строке.
        described = cli.describe_target(
            "postgresql+psycopg://user:secret@db.example.com:5432/prod"
        )
        assert described == (
            "postgresql+psycopg host=db.example.com port=5432 database=prod"
        )
        assert (
            cli.describe_target("sqlite:////tmp/derma.db")
            == "sqlite database=/tmp/derma.db"
        )

    def test_main_resyncs_passed_url_not_env(self, tmp_path, monkeypatch, capsys):
        """End-to-end репро владельца: DATABASE_URL окружения (staging) +
        аргумент (prod) — пересчёт обязан пойти по аргументу, файл
        окружения не создаётся; цель печатается ПЕРЕД записью."""
        from sqlalchemy import create_engine

        from app.db.base_class import Base
        from app.models.derma_examination import DermaExamination
        from app.models.derma_history import DermaHistoryEntry
        from app.models.derma_procedure import DermaProcedure
        from app.models.emr_v2 import EMRRecord
        from app.models.visit import Visit

        target = tmp_path / "argdb.db"
        env_db = tmp_path / "envdb.db"
        engine = create_engine(f"sqlite:///{target}")
        Base.metadata.create_all(
            engine,
            tables=[
                Visit.__table__,
                EMRRecord.__table__,
                DermaExamination.__table__,
                DermaProcedure.__table__,
                DermaHistoryEntry.__table__,
            ],
        )
        engine.dispose()

        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{env_db}")
        monkeypatch.setenv("CONFIRM_DERMA_HISTORY_RESYNC", "1")

        rc = cli.main(["--database-url", f"sqlite:///{target}"])

        assert rc == 0
        captured = capsys.readouterr()
        # цель напечатана ДО любой записи и называет именно аргумент
        # (точное равенство, не substring — см. CodeQL-примечание выше)
        out_lines = captured.out.splitlines()
        assert out_lines[0] == (
            f"derma history resync target: sqlite database={target}"
        )
        assert out_lines[1] == (
            "mode: FULL rebuild — требует остановленной записи "
            "(runbook: окно обслуживания; под трафиком — --visit-ids)"
        )
        assert target.exists()
        assert not env_db.exists()  # окружение не тронуто

    def test_main_scoped_mode_skips_global_delete(self, tmp_path, monkeypatch, capsys):
        """--visit-ids: scoped-режим без глобального DELETE — runbook-режим
        для живого трафика (P2-3); визит без ЭМК — пустой no-op."""
        from sqlalchemy import create_engine

        from app.db.base_class import Base
        from app.models.derma_examination import DermaExamination
        from app.models.derma_history import DermaHistoryEntry
        from app.models.derma_procedure import DermaProcedure
        from app.models.emr_v2 import EMRRecord
        from app.models.visit import Visit

        target = tmp_path / "scoped.db"
        engine = create_engine(f"sqlite:///{target}")
        Base.metadata.create_all(
            engine,
            tables=[
                Visit.__table__,
                EMRRecord.__table__,
                DermaExamination.__table__,
                DermaProcedure.__table__,
                DermaHistoryEntry.__table__,
            ],
        )
        engine.dispose()

        monkeypatch.setenv("CONFIRM_DERMA_HISTORY_RESYNC", "1")
        rc = cli.main(["--database-url", f"sqlite:///{target}", "--visit-ids", "1,2"])

        assert rc == 0
        captured = capsys.readouterr()
        out_lines = captured.out.splitlines()
        assert out_lines[1] == (
            "mode: scoped, visit_ids=[1, 2] "
            "(без глобального DELETE, безопасно под трафиком)"
        )
        assert "  emr_records: 0" in captured.out

    def test_main_refuses_without_confirmation(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CONFIRM_DERMA_HISTORY_RESYNC", raising=False)
        with pytest.raises(RuntimeError, match="CONFIRM_DERMA_HISTORY_RESYNC"):
            cli.main(["--database-url", f"sqlite:///{tmp_path}/x.db"])
