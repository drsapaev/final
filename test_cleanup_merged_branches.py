import unittest
from unittest.mock import patch

from scripts.cleanup_merged_branches import (
    Evidence,
    build_cleanup_plan,
    inspect_local_base_status,
    list_graph_merged_branches,
    list_local_branches,
    local_branch_for_base,
    parse_ahead_behind,
    parse_pr_number_from_branch,
    parse_worktree_branches,
    parse_worktree_branch_paths,
)


class CleanupMergedBranchesTests(unittest.TestCase):
    def test_parse_worktree_branches_collects_checked_out_refs(self):
        porcelain = """
worktree C:/final
HEAD abc123
branch refs/heads/codex/example

worktree C:/tmp/repo
HEAD def456
detached

worktree C:/tmp/main
HEAD 123abc
branch refs/heads/main
"""

        self.assertEqual(
            parse_worktree_branches(porcelain),
            frozenset({"codex/example", "main"}),
        )
        self.assertEqual(
            parse_worktree_branch_paths(porcelain),
            {"codex/example": "C:/final", "main": "C:/tmp/main"},
        )

    def test_plan_keeps_active_and_protected_branches(self):
        plan = build_cleanup_plan(
            branches=["main", "codex/done", "codex/active"],
            graph_merged=["main", "codex/done", "codex/active"],
            active_worktree_branches=["codex/active"],
            protected_branches=["main"],
            repo=None,
            include_github=False,
        )

        self.assertEqual([candidate.branch for candidate in plan.candidates], ["codex/done"])
        self.assertEqual(
            {kept.branch: kept.reason for kept in plan.kept},
            {
                "codex/active": "checked out by an active worktree",
                "main": "protected branch name",
            },
        )

    def test_plan_uses_github_merged_evidence_for_squash_branch(self):
        with patch(
            "scripts.cleanup_merged_branches.branch_has_merged_pr",
            return_value="PR #123 merged at 2026-05-22T00:00:00Z: title",
        ):
            plan = build_cleanup_plan(
                branches=["codex/squashed"],
                graph_merged=[],
                active_worktree_branches=[],
                protected_branches=[],
                repo="drsapaev/final",
                include_github=True,
            )

        self.assertEqual(len(plan.candidates), 1)
        self.assertEqual(plan.candidates[0].branch, "codex/squashed")
        self.assertEqual(plan.candidates[0].evidence, Evidence.GITHUB_MERGED)

    def test_plan_keeps_unknown_unmerged_branch(self):
        with patch("scripts.cleanup_merged_branches.branch_has_merged_pr", return_value=None):
            plan = build_cleanup_plan(
                branches=["codex/not-found"],
                graph_merged=[],
                active_worktree_branches=[],
                protected_branches=[],
                repo="drsapaev/final",
                include_github=True,
            )

        self.assertEqual(plan.candidates, ())
        self.assertEqual(plan.kept[0].reason, "no merged evidence found")

    def test_parse_pr_number_from_local_pr_branch(self):
        self.assertEqual(parse_pr_number_from_branch("pr-854"), 854)
        self.assertEqual(parse_pr_number_from_branch("pr/854"), 854)
        self.assertIsNone(parse_pr_number_from_branch("codex/pr-854"))

    def test_local_branch_for_origin_base(self):
        self.assertEqual(local_branch_for_base("origin/main"), "main")
        self.assertEqual(local_branch_for_base("origin/develop"), "develop")
        self.assertIsNone(local_branch_for_base("upstream/main"))
        self.assertIsNone(local_branch_for_base("origin/release/one"))

    def test_parse_ahead_behind(self):
        self.assertEqual(parse_ahead_behind("0\t4\n"), (0, 4))

    def test_list_local_branches_uses_refs_heads_only(self):
        with patch("scripts.cleanup_merged_branches.git_lines", return_value=("main", "codex/task")) as git_lines:
            branches = list_local_branches()

        self.assertEqual(branches, ("main", "codex/task"))
        git_lines.assert_called_once_with(("for-each-ref", "--format=%(refname:short)", "refs/heads"))

    def test_list_graph_merged_branches_uses_refs_heads_only(self):
        with patch("scripts.cleanup_merged_branches.git_lines", return_value=("main",)) as git_lines:
            branches = list_graph_merged_branches("origin/main")

        self.assertEqual(branches, ("main",))
        git_lines.assert_called_once_with(
            ("for-each-ref", "--merged=origin/main", "--format=%(refname:short)", "refs/heads")
        )

    def test_inspect_local_base_status_reports_behind(self):
        with patch("scripts.cleanup_merged_branches.run_command") as run_command:
            run_command.return_value.stdout = "0\t3\n"
            with patch("scripts.cleanup_merged_branches.worktree_is_clean", return_value=True):
                status = inspect_local_base_status(
                    base="origin/main",
                    branches=["main", "codex/task"],
                    worktree_branch_paths={"main": "C:/repo-main"},
                )

        self.assertIsNotNone(status)
        self.assertEqual(status.branch, "main")
        self.assertEqual(status.behind, 3)
        self.assertEqual(status.ahead, 0)
        self.assertTrue(status.clean)
        self.assertIn("behind origin/main by 3", status.detail)

    def test_inspect_local_base_status_reports_ahead_as_manual_review(self):
        with patch("scripts.cleanup_merged_branches.run_command") as run_command:
            run_command.return_value.stdout = "2\t0\n"
            status = inspect_local_base_status(
                base="origin/main",
                branches=["main"],
                worktree_branch_paths={},
            )

        self.assertIsNotNone(status)
        self.assertEqual(status.ahead, 2)
        self.assertIn("manual review required", status.detail)


if __name__ == "__main__":
    unittest.main()
