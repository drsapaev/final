"""Verify shell smoke verdicts without touching real services or credentials."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "smoke_test_staging.sh"


def staging(tmp_path):
    for path in ("scripts", "bin", "backend/tests/unit", "frontend/node_modules"):
        (tmp_path / path).mkdir(parents=True)
    shutil.copy2(SCRIPT, tmp_path / "scripts")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".git/hooks/pre-commit").touch()
    (tmp_path / ".pre-commit-config.yaml").touch()

    python = tmp_path / "bin/python"
    python.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$*\" in\n"
        '  *capture_exception*) exit "${STUB_SENTRY_RC:-0}" ;;\n'
        '  *RequireAiFeature*) exit "${STUB_AI_RC:-0}" ;;\n'
        '  *test_pii_masker.py*) exit "${STUB_PII_TEST_RC:-0}" ;;\n'
        "esac\n"
    )
    python.chmod(0o755)
    for command in ("bandit", "npm", "pre-commit"):
        (tmp_path / "bin" / command).symlink_to("/bin/true")

    def run(*args, **overrides):
        env = {
            "PATH": f"{tmp_path / 'bin'}:{os.defpath}",
            "SENTRY_DSN": "stub",
            "DATABASE_URL": "stub",
            "ARQ_TEST_REDIS_URL": "stub",
            **overrides,
        }
        return subprocess.run(
            ["bash", "scripts/smoke_test_staging.sh", *args],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    return run


class SmokeVerdictTests(unittest.TestCase):
    def test_smoke_verdict(self):
        cases = [
            ((), {"SENTRY_DSN": ""}, 0),
            (("--strict",), {"SENTRY_DSN": ""}, 2),
            (("--strict",), {"ARQ_TEST_REDIS_URL": ""}, 2),
            (("--strict",), {}, 0),
            (("--strict",), {"STUB_SENTRY_RC": "2"}, 1),
            (("--strict",), {"STUB_AI_RC": "1"}, 1),
            (("--strict",), {"SENTRY_DSN": "", "STUB_PII_TEST_RC": "2"}, 1),
            (("--unknown",), {}, 64),
        ]
        for args, env, expected in cases:
            with self.subTest(args=args, env=env), tempfile.TemporaryDirectory() as tmp:
                result = staging(Path(tmp))(*args, **env)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertNotIn("System is ready for production deploy", result.stdout)
                if args == ("--strict",) and expected == 0:
                    self.assertIn("not full staging validation", result.stdout)
