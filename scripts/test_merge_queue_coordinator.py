"""Pure request-sequence tests plus wiring assertions for the GitHub merge slot."""

import unittest
from copy import deepcopy
from pathlib import Path

import yaml
from merge_queue_coordinator import APP_LOGIN, REPOSITORY, Blocked, Coordinator

BASE, HEAD, SYNC, OTHER = (digit * 40 for digit in "abcd")
REPO = f"repos/{REPOSITORY}"
PR = f"{REPO}/pulls/10"
ROOT = Path(__file__).resolve().parents[1]


class GitHub:
    def __init__(self):
        self.calls = []
        self.t = 0
        self.on_sleep = lambda: None
        self.base, self.head = BASE, HEAD
        self.auto = None
        self.reviews = []
        self.comparison = "ahead"
        self.status = "clean"
        self.open = True
        self.fork = False
        self.parents = [HEAD, BASE]
        self.mergeable = True
        self.sync_head = SYNC
        self.update_error = None

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        self.on_sleep()

    def request(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        if endpoint == f"{REPO}/git/ref/heads/main":
            return {"object": {"sha": self.base}}
        if endpoint.startswith(f"{REPO}/pulls?"):
            return [[{"number": 20, "auto_merge": self.auto}]]
        if endpoint == PR:
            return {
                "state": "open" if self.open else "closed", "draft": False,
                "base": {"ref": "main"}, "auto_merge": None,
                "head": {"ref": "topic", "sha": self.head,
                         "repo": {"full_name": "other/fork" if self.fork else REPOSITORY}},
                "user": {"login": "contributor"}, "mergeable": self.mergeable,
                "mergeable_state": self.status,
            }
        if endpoint.startswith(f"{REPO}/compare/"):
            return {"status": self.comparison}
        if endpoint == f"{PR}/update-branch":
            if self.update_error:
                raise Blocked(self.update_error)
            self.head = self.sync_head
            return {"message": "Updating"}
        if endpoint.startswith(f"{REPO}/commits/"):
            return {"parents": [{"sha": value} for value in self.parents]}
        if endpoint.startswith(f"{PR}/reviews?"):
            return [deepcopy(self.reviews)]
        raise AssertionError(endpoint)

    def review(self, commit_id, state="APPROVED", login=APP_LOGIN):
        self.reviews.append({"user": {"login": login}, "commit_id": commit_id, "state": state})


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.gh = GitHub()
        self.queue = Coordinator(self.gh.request, "10", sleep=self.gh.sleep, clock=self.gh.now)

    def test_current_head_needs_no_update(self):
        self.assertEqual(self.queue.prepare(HEAD), (BASE, HEAD))
        self.assertFalse(any(args.get("method") == "PUT" for _, args in self.gh.calls))

    def test_stale_base_synchronizes_only_exact_request(self):
        self.gh.comparison = "diverged"
        self.assertEqual(self.queue.prepare(HEAD), (BASE, SYNC))
        self.assertIn((f"{PR}/update-branch", {"method": "PUT", "body": {"expected_head_sha": HEAD}}), self.gh.calls)

    def test_changed_request_is_not_updated(self):
        with self.assertRaisesRegex(Blocked, "request is stale"):
            self.queue.prepare(OTHER)
        self.assertFalse(any(args.get("method") == "PUT" for _, args in self.gh.calls))

    def test_conflict_and_fork_do_not_get_write_attempts(self):
        self.gh.comparison, self.gh.mergeable = "diverged", False
        with self.assertRaisesRegex(Blocked, "resolve conflicts"):
            self.queue.prepare(HEAD)
        self.gh.fork = True
        with self.assertRaisesRegex(Blocked, "same-repo"):
            self.queue.prepare(HEAD)
        self.assertFalse(any(args.get("method") == "PUT" for _, args in self.gh.calls))

    def test_unexpected_sync_commit_is_rejected(self):
        self.gh.comparison = "diverged"
        self.gh.parents = [HEAD, OTHER]
        with self.assertRaisesRegex(Blocked, "Unexpected PR head"):
            self.queue.prepare(HEAD)

    def test_uncertain_update_has_no_retry(self):
        self.gh.comparison = "diverged"
        self.gh.update_error = "GitHub API failed: HTTP 503."
        with self.assertRaisesRegex(Blocked, "503"):
            self.queue.prepare(HEAD)
        self.assertEqual(sum(args.get("method") == "PUT" for _, args in self.gh.calls), 1)

    def test_native_auto_merge_is_not_ignored(self):
        self.gh.auto = {}
        with self.assertRaisesRegex(Blocked, "Competing native"):
            self.queue.prepare(HEAD)
        self.gh.review(HEAD)
        with self.assertRaisesRegex(Blocked, "Competing native"):
            self.queue.validate(BASE, HEAD, timeout=30)

    def test_only_exact_app_approval_plus_clean_required_checks_passes(self):
        self.gh.status = "blocked"
        self.gh.review(OTHER)
        self.gh.review(HEAD, login="someone-else")
        with self.assertRaisesRegex(Blocked, "Timed out"):
            self.queue.validate(BASE, HEAD, timeout=30)
        self.gh.status = "clean"
        with self.assertRaisesRegex(Blocked, "Timed out"):
            self.queue.validate(BASE, HEAD, timeout=30)
        self.gh.review(HEAD)
        self.queue.validate(BASE, HEAD, timeout=30)

    def test_approval_does_not_override_blocked_checks(self):
        self.gh.review(HEAD)
        self.gh.status = "blocked"
        with self.assertRaisesRegex(Blocked, "Timed out"):
            self.queue.validate(BASE, HEAD, timeout=30)

    def test_later_dismissal_and_requested_changes_do_not_merge(self):
        self.gh.review(HEAD)
        self.gh.review(HEAD, "DISMISSED")
        with self.assertRaisesRegex(Blocked, "Timed out"):
            self.queue.validate(BASE, HEAD, timeout=30)
        self.gh.review(HEAD, "CHANGES_REQUESTED")
        with self.assertRaisesRegex(Blocked, "requested changes"):
            self.queue.validate(BASE, HEAD, timeout=30)

    def test_main_advance_from_uncoordinated_writer_invalidates_wait(self):
        self.gh.status = "blocked"
        self.gh.on_sleep = lambda: setattr(self.gh, "base", OTHER)
        with self.assertRaisesRegex(Blocked, "main moved"):
            self.queue.validate(BASE, HEAD, timeout=30)

    def test_pending_slot_detects_head_drift(self):
        self.gh.on_sleep = lambda: setattr(self.gh, "head", OTHER)
        with self.assertRaisesRegex(Blocked, "PR changed"):
            self.queue.validate(BASE, HEAD, timeout=30)

    def test_sequential_slots_each_pin_current_main(self):
        self.gh.status = "blocked"

        def finish_checks():
            self.gh.status = "clean"
            self.gh.review(HEAD)

        self.gh.on_sleep = finish_checks
        self.queue.validate(BASE, HEAD, timeout=60)
        self.gh.base, self.gh.head, self.gh.comparison = OTHER, SYNC, "ahead"
        self.assertEqual(self.queue.prepare(SYNC), (OTHER, SYNC))


class WorkflowTests(unittest.TestCase):
    def test_shared_group_is_opt_in_and_does_not_lock_approval(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/codex-pr-app.yml").read_text())
        group = workflow["concurrency"]
        self.assertEqual(group["queue"], "max")
        self.assertFalse(group["cancel-in-progress"])
        self.assertIn("inputs.operation == 'merge'", group["group"])
        self.assertIn("vars.FINAL_MERGE_QUEUE_ENABLED == 'true'", group["group"])
        self.assertIn("'final-main-merge-slot'", group["group"])
        job = next(iter(workflow["jobs"].values()))
        self.assertNotIn("concurrency", job)
        self.assertIn("github.triggering_actor == github.repository_owner", job["if"])
        self.assertEqual(job["environment"], "codex-pr-app")
        self.assertEqual(job["permissions"], {"contents": "read", "pull-requests": "read"})
        steps = job["steps"]
        rendered = "\n".join(step.get("run", "") for step in steps)
        self.assertNotIn("actions/checkout", str(steps))
        self.assertIn("github.workflow_sha", str(steps))
        self.assertIn("&& vars.FINAL_MERGE_QUEUE_ENABLED", steps[0]["if"])
        self.assertLess(rendered.index('prepare'), rendered.index(' wait'))
        self.assertLess(rendered.index(' wait'), rendered.index('actual_base'))
        self.assertLess(rendered.index('actual_base'), rendered.index('f"{endpoint}/merge"'))
        self.assertNotIn("--admin", rendered)
        self.assertIn('"sha": head_sha, "merge_method": "squash"', rendered)


if __name__ == "__main__":
    unittest.main()
