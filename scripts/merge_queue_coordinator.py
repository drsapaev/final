"""Opt-in queue for the protected Codex App. Never checks out a PR."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPOSITORY = "drsapaev/final"
APP_LOGIN = "drsapaev-final-codex-pr[bot]"
SHA = re.compile(r"[a-f0-9]{40}")
NUMBER = re.compile(r"[1-9][0-9]*")


class Blocked(RuntimeError):
    """A terminal, fail-closed response for this slot."""


def api(endpoint, *, method="GET", body=None, paginate=False):
    command = ["gh", "api", "--method", method, endpoint]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    if body is not None:
        command.extend(["--input", "-"])
    result = subprocess.run(
        command, input=json.dumps(body) if body is not None else None,
        capture_output=True, encoding="utf-8", check=False, timeout=40,
    )
    if result.returncode:
        # Do not emit raw API bodies, tokens, or PR-authored text.
        status = re.search(r"HTTP ([0-9]{3})", result.stderr)
        raise Blocked(f"GitHub {method} request failed: HTTP {status[1] if status else 'unknown'}.")
    return json.loads(result.stdout)


class Coordinator:
    def __init__(self, request, number, report=print, sleep=time.sleep, clock=time.monotonic):
        if not NUMBER.fullmatch(number):
            raise Blocked("Invalid PR number.")
        self.request = request
        self.number = number
        self.repo = f"repos/{REPOSITORY}"
        self.endpoint = f"{self.repo}/pulls/{number}"
        self.report = report
        self.sleep = sleep
        self.clock = clock

    def main(self):
        sha = self.request(f"{self.repo}/git/ref/heads/main")["object"]["sha"]
        if not SHA.fullmatch(sha):
            raise Blocked("Invalid main SHA.")
        return sha

    def pr(self):
        pr = self.request(self.endpoint)
        head_repo = pr["head"].get("repo") or {}
        if (
            pr["state"] != "open" or pr["draft"] or pr["base"]["ref"] != "main"
            or head_repo.get("full_name") != REPOSITORY or pr["head"]["ref"] == "main"
            or pr["user"]["login"] == APP_LOGIN or not SHA.fullmatch(pr["head"]["sha"])
        ):
            raise Blocked("Expected an open, ready, same-repo PR into main.")
        return pr

    def ensure_no_native_auto_merge(self):
        for page in self.request(f"{self.repo}/pulls?state=open&base=main&per_page=100", paginate=True):
            for pr in page:
                if "auto_merge" not in pr:
                    raise Blocked("Unable to verify whether a competing auto-merge is armed.")
                if pr["auto_merge"] is not None:
                    raise Blocked(f"Competing native auto-merge armed on PR #{int(pr['number'])}.")

    def wait(self, condition, timeout, failure):
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            result = condition()
            if result:
                return result
            self.sleep(min(20, max(0, deadline - self.clock())))
        raise Blocked(failure)

    def prepare(self, expected_head):
        if not SHA.fullmatch(expected_head):
            raise Blocked("Invalid request SHA.")
        self.ensure_no_native_auto_merge()
        base = self.main()
        current = self.pr()
        if current["head"]["sha"] != expected_head:
            raise Blocked("Queued request is stale; the PR head changed while waiting.")
        comparison = self.request(f"{self.repo}/compare/{base}...{expected_head}")
        if comparison["status"] in {"ahead", "identical"}:
            if self.main() != base or self.pr()["head"]["sha"] != expected_head:
                raise Blocked("References moved during slot acquisition.")
            return base, expected_head
        if comparison["status"] not in {"diverged", "behind"} or current["mergeable"] is False:
            raise Blocked("GitHub cannot safely synchronize the PR; resolve conflicts and requeue.")
        if self.main() != base or self.pr()["head"]["sha"] != expected_head:
            raise Blocked("References moved before synchronization.")
        self.request(f"{self.endpoint}/update-branch", method="PUT",
                     body={"expected_head_sha": expected_head})

        def synchronized():
            if self.main() != base:
                raise Blocked("main moved outside the queue during synchronization.")
            new = self.pr()["head"]["sha"]
            if new == expected_head:
                return None
            commit = self.request(f"{self.repo}/commits/{new}")
            if [parent["sha"] for parent in commit["parents"]] != [expected_head, base]:
                raise Blocked("Unexpected PR head change; do not reuse validation.")
            return new

        head = self.wait(synchronized, 180, "Synchronization not confirmed; verify the PR before requeueing.")
        return base, head

    def approved(self, head):
        decision = None
        for page in self.request(f"{self.endpoint}/reviews?per_page=100", paginate=True):
            for review in page:
                if (
                    (review.get("user") or {}).get("login") == APP_LOGIN
                    and review["commit_id"] == head
                    and review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
                ):
                    decision = review["state"]
        if decision == "CHANGES_REQUESTED":
            raise Blocked("The Codex App requested changes; fix and requeue.")
        return decision == "APPROVED"

    def validate(self, base, head, timeout=4500):
        if not SHA.fullmatch(base) or not SHA.fullmatch(head):
            raise Blocked("Invalid pinned references.")

        def ready():
            if self.main() != base:
                raise Blocked("main moved outside the queue; no stale merge attempted.")
            pr = self.pr()
            if pr["head"]["sha"] != head:
                raise Blocked("PR changed after slot preparation; requeue the new revision.")
            if pr["auto_merge"] is not None:
                raise Blocked("A native auto-merge was armed while this slot was active.")
            if pr["mergeable"] is False:
                raise Blocked("GitHub reported a conflict; resolve it and requeue.")
            return pr["mergeable_state"] == "clean" and self.approved(head)

        self.wait(ready, timeout, "Timed out waiting for exact App approval and protected checks.")
        self.ensure_no_native_auto_merge()
        if self.main() != base or self.pr()["head"]["sha"] != head or not self.approved(head):
            raise Blocked("References or approval changed before protected merge.")


def write_output(**fields):
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        for key, value in fields.items():
            print(f"{key}={value}", file=stream)


def run():
    if (os.environ["GITHUB_REPOSITORY"] != REPOSITORY or os.environ["GITHUB_REF"] != "refs/heads/main"
            or os.environ["GITHUB_ACTOR"] != "drsapaev"
            or os.environ["GITHUB_TRIGGERING_ACTOR"] != "drsapaev"):
        raise Blocked("Main and owner dispatch are required.")
    coordinator = Coordinator(api, os.environ["PR_NUMBER"], report=lambda s: print(s, flush=True))
    stage = sys.argv[1]
    if stage == "prepare":
        base, head = coordinator.prepare(os.environ["HEAD_SHA"])
        write_output(base=base, head=head)
        line = (f"Active slot for #{coordinator.number}: base `{base}`, final head `{head}`. "
                "Run the applicable gate and review on this head, then submit App approval.")
        coordinator.report(line)
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            print(line, file=stream)
    elif stage == "wait":
        coordinator.validate(os.environ["PINNED_BASE"], os.environ["HEAD_SHA"])
    else:
        raise Blocked("Unknown queue stage.")


if __name__ == "__main__":
    try:
        run()
    except (Blocked, KeyError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc) if isinstance(exc, Blocked) else "Queue stopped: unexpected GitHub response.", file=sys.stderr)
        sys.exit(1)
