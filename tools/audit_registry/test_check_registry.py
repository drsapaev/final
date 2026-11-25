import contextlib
import io
import unittest
from unittest.mock import call, patch

from tools.audit_registry import check_registry


class RegistryConsistencyTests(unittest.TestCase):
    def assert_rejected(self, function, entries, message):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            function(entries, None)
        self.assertIn(message, output.getvalue())

    @patch.object(check_registry, "fetch_github_json")
    def test_issue_check_requires_matching_checkbox_state(self, fetch):
        entries = [{"id": "AUTH-BE-001", "checked": True}]
        fetch.return_value = {"body": "- [x] `AUTH-BE-001` — verified"}
        check_registry.crosscheck_issue(entries, None)

        fetch.return_value = {"body": "- [ ] `AUTH-BE-001` — pending"}
        self.assert_rejected(check_registry.crosscheck_issue, entries, "checkbox state differs")

    @patch.object(check_registry, "fetch_github_json")
    def test_issue_check_rejects_duplicate_or_missing_checklist_ids(self, fetch):
        entries = [{"id": "AUTH-BE-001", "checked": False}]
        fetch.return_value = {"body": "- [ ] `AUTH-BE-001`\n- [x] `AUTH-BE-001`"}
        self.assert_rejected(check_registry.crosscheck_issue, entries, "duplicate checklist id")

        fetch.return_value = {"body": "No checklist available"}
        self.assert_rejected(check_registry.crosscheck_issue, entries, "no recognizable checklist")

    @patch.object(check_registry, "fetch_github_json")
    def test_fixed_entries_require_the_actual_merged_pull_request(self, fetch):
        entries = [
            {"id": "AUTH-BE-001", "status": "FIXED_VERIFIED_ON_MAIN", "fix_pr": "#42", "merge_sha": "abcdef123"},
            {"id": "AUTH-BE-002", "status": "FIXED_VERIFIED_ON_MAIN", "fix_pr": 42, "merge_sha": "abcdef123"},
        ]
        fix = "abcdef123" + "0" * 31
        main = "b" * 40
        fetch.side_effect = [
            {"merged": True, "merge_commit_sha": fix},
            {"object": {"sha": main}},
            {"status": "ahead", "merge_base_commit": {"sha": fix}},
        ]
        check_registry.verify_merged_pull_requests(entries, None)
        self.assertEqual(
            fetch.call_args_list,
            [
                call(f"{check_registry.GITHUB_REPO_API}/pulls/42", None),
                call(f"{check_registry.GITHUB_REPO_API}/git/ref/heads/main", None),
                call(f"{check_registry.GITHUB_REPO_API}/compare/{fix}...{main}?per_page=1", None),
            ],
        )

        fetch.side_effect = None
        fetch.return_value = {"merged": False, "merge_commit_sha": "abcdef123" + "0" * 31}
        self.assert_rejected(check_registry.verify_merged_pull_requests, entries, "not merged")
        fetch.return_value = {"merged": True, "merge_commit_sha": "fedcba987" + "0" * 31}
        self.assert_rejected(check_registry.verify_merged_pull_requests, entries, "not merged with recorded SHA")

    @patch.object(check_registry, "fetch_github_json")
    def test_fixed_entry_rejects_merge_not_reachable_from_main(self, fetch):
        fix, main = "a" * 40, "b" * 40
        entries = [
            {"id": "AUTH-BE-003", "status": "FIXED_VERIFIED_ON_MAIN", "fix_pr": 43, "merge_sha": fix},
        ]
        for status, base in (("behind", main), ("diverged", main), ("ahead", main), ("ahead", None)):
            with self.subTest(status=status, base=base):
                fetch.side_effect = [
                    {"merged": True, "merge_commit_sha": fix},
                    {"object": {"sha": main}},
                    {"status": status, "merge_base_commit": {"sha": base}},
                ]
                self.assert_rejected(check_registry.verify_merged_pull_requests, entries, "not verified in canonical main")

    @patch.object(check_registry, "fetch_github_json")
    def test_fixed_entry_accepts_main_tip_and_rejects_unavailable_main_pin(self, fetch):
        fix = "a" * 40
        entries = [
            {"id": "AUTH-BE-004", "status": "FIXED_VERIFIED_ON_MAIN", "fix_pr": 44, "merge_sha": fix},
        ]
        merged = {"merged": True, "merge_commit_sha": fix}
        fetch.side_effect = [
            merged, {"object": {"sha": fix}}, {"status": "identical", "merge_base_commit": {"sha": fix}},
        ]
        check_registry.verify_merged_pull_requests(entries, None)
        fetch.side_effect = [merged, {"object": {"sha": fix[:8]}}]
        self.assert_rejected(check_registry.verify_merged_pull_requests, entries, "could not pin")

    def test_final_closure_rejects_unchecked_fixed_entry(self):
        entries = [{"id": "AUTH-BE-001", "status": "FIXED_VERIFIED_ON_MAIN", "checked": False}]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            check_registry.final_closure(entries)
        self.assertIn("owner checklist entries remain unchecked", output.getvalue())

        entries[0]["checked"] = True
        with contextlib.redirect_stdout(io.StringIO()):
            check_registry.final_closure(entries)


if __name__ == "__main__":
    unittest.main()
