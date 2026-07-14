import unittest
from argparse import Namespace
from unittest.mock import patch

from scripts.run_pr_review_gate_checks import _is_dependabot_author, _read_pr_author


class PRReviewGateRunnerTests(unittest.TestCase):
    def test_accepts_dependabot_pull_request_author(self):
        self.assertTrue(_is_dependabot_author("dependabot[bot]"))

    def test_accepts_gh_cli_dependabot_author(self):
        self.assertTrue(_is_dependabot_author("app/dependabot"))

    def test_rejects_regular_author(self):
        self.assertFalse(_is_dependabot_author("drsapaev"))

    def test_reads_default_pr_author_environment(self):
        args = Namespace(author=None, author_env=None)

        with patch.dict("os.environ", {"PR_AUTHOR": "dependabot[bot]"}):
            self.assertEqual(_read_pr_author(args), "dependabot[bot]")


if __name__ == "__main__":
    unittest.main()
