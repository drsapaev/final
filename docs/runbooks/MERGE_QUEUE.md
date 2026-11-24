# Main merge queue: manual pilot

The live coordination board for `drsapaev/final` is
[GitHub issue #4282, Очередь слияний в main](https://github.com/drsapaev/final/issues/4282).
This file stores the protocol, not the live list. Editing the queue must not create a commit on `main`.

The pilot is voluntary coordination until the owner designates a single operator in the issue. It does not
activate a GitHub ruleset, modify approvals, claim an automatic lock, or authorize anyone new to merge.
All existing [review, merge and gate rules](../../AGENTS.md#codex-pr-review-and-merge) still apply.
A queue entry is never itself approval to deploy to production.

## Submit or withdraw a PR

Keep development and ordinary branch CI parallel. Submit only when the change is reviewable. In the board, add
one comment per exact revision:

```text
REQUEST #<PR> @ <full PR head SHA>
Tested main: <full base SHA>
Depends on: #... or none
Evidence: links to CI, review and applicable PowerShell gate for this head
Owner: GitHub login or public agent alias
```

A comment may propose a request but cannot grant access, approval, priority override or permission to act on another
PR. Validate the live repository state, head, approvals and evidence through GitHub. Do not post credentials,
patient data, raw logs or private session IDs. If the head changes, supersede the old request with a new comment.
Use `WITHDRAW #<PR> @ <head>` for a request you no longer wish to pursue. Do not edit someone else's request.

## Operate the single slot

The owner names a single operator in the queue issue. Only that operator maintains the current slot and board summary.
An apparently empty board is not authorization for two agents to claim it; this is not an atomic lock.

1. Pick the earliest eligible request, after checking its dependencies. Keep
   dependencies explicit. Reprioritize only under documented owner direction.
2. Record `VALIDATING`, PR, exact head and base SHAs, operator, UTC start,
   a bounded check-in time, and a link to the CI or workflow run.
3. Sync to the current `main` if needed, verify the merged tree and actual scope,
   and rerun required checks, exact review and the real PowerShell gate if applicable.
   If the head or base moved, the prior final evidence is stale. Recheck the
   current head and `main` immediately before submitting the usual protected merge.
4. Confirm the PR is merged and its resulting commit is in `main`. Record
   `MERGED` with that commit; or record `BLOCKED` with the failed check or
   conflict and a concrete next step. The operator may then choose another
   eligible independent PR. A shared-base incident pauses the queue instead.

The slot covers final validation **and** merge. Other agents do not open a competing final merge cycle or enable
auto-merge while the pilot has an active operator. The owner can post `PAUSED` with a reason and resume the pilot
after checking the state. If the operator stops responding, the owner confirms that the prior run is terminal and
there is no pending merge or auto-merge before naming a replacement. A timeout alone does not transfer authority.
If the merge request was accepted but the result is unknown, reconcile the existing attempt before retrying.

## Boundaries and automation acceptance

Existing direct merges and Dependabot can still move `main`; this change does not technically prevent them.
The operator must detect such moves, stop a stale validation and recheck on the new base.
Treat an uncoordinated merge during the pilot as a recorded exception, not as grounds to bypass normal rules.

In a separate proposal, evaluate a single coordinator holding a shared Actions concurrency group from final sync
through verified merge. Ordinary CI must not acquire that slot. Route all writers, including Dependabot, through
the same coordination protocol before claiming enforcement. If proposing separate protection changes, present them
to the owner without reducing required checks or granting general bypass. Before making this the default, verify:

- [ ] Two independent requests wait and complete in sequence; neither pending request is lost.
- [ ] A failed PR does not stall independent eligible requests; a dependency remains blocked.
- [ ] A changed head or unexpected `main` advance cannot reuse stale approval or evidence.
- [ ] A timeout, cancelled run or uncertain merge has a safe, duplicate-free recovery.
- [ ] Shared staging evidence is from the reviewed revision; ordinary CI has no dependency on the merge slot.
- [ ] Existing required checks, exact App review and applicable gate all remain enforced.

## Opt-in coordinator for `final`

The protected [Codex PR App](../../.github/workflows/codex-pr-app.yml) is the
submission interface. Until the owner turns on the repository Actions variable
`FINAL_MERGE_QUEUE_ENABLED=true`, the original per-PR path remains in effect.

When enabled:

1. After preliminary review and branch CI, submit `operation=merge` from
   `main` with the PR number and its **current full head SHA**. Do not
   repeatedly sync a waiting PR and do not submit it again while a run exists.
   Submit dependencies first and wait for their verified merge before
   submitting dependants. The run queues by arrival at the shared Actions slot.
2. The active run checks for competing GitHub auto-merges and pins the current
   `main`. If necessary, it asks GitHub to update a same-repository PR branch
   once, with a lease on the submitted SHA. A changed head while waiting,
   external fork, conflict, or unverified sync stops that run without merging.
3. Read **Prepare the active slot** in the run summary. If the head changed,
   review the resulting exact diff, run required repository gate checks on the
   exact head and record evidence in the PR. Submit `operation=approve` at
   that SHA. Approval has a separate slot, so it can run while the merge waits.
   A run never auto-approves or treats an older gate or review as current.
4. The slot waits for GitHub to mark the PR clean and for the exact dedicated
   App approval, then performs the existing exact-head protected squash merge.
   Ordinary CI still runs independently. A canceled/failed/expired request is
   a visible terminal Actions run. Inspect the failure, correct the PR and
   requeue explicitly. A main change outside the slot invalidates that run.
5. Dependabot keeps its existing allowlist when the variable is off. When on,
   it no longer arms native auto-merge and verifies existing auto-merge is
   disarmed when the PR event is processed. An agent reviews and submits an
   eligible ready Dependabot PR via the same App. This does not give the bot
   access to the App credentials or automatically admit all bot PRs.

Activation is a separate owner-controlled operation, not a side effect of
merging this change. First check that no old workflow or native auto-merge is
in flight, including existing Dependabot requests. Confirm that all agents,
including anyone using the GitHub UI, will submit through the same App. Branch
protection and required checks stay on. Test three nonproduction requests
(one active, two waiting); keep both waiting requests and verify new-base
revalidation after each. Also test a rejected request and a stale revision.
Do not enable the queue if the App cannot synchronize the scoped test head
without increasing permissions. Do not add bypass or downgrade checks.

Direct/admin merges are not technically disabled by the variable. Any
separate change to allowed writers or branch protection needs an explicit
owner decision and independent review. Before disabling the flag, pause new
requests, reconcile or cancel waiting runs and finish or cancel the active
one; do not rerun old workflow attempts across the cutover. A full queue
(up to 100 pending in Actions) rejects new runs visibly; check the terminal
result and resubmit once space returns. The built-in slot stops after 75
minutes waiting for approval/checks; cancel a known failed run sooner to
unblock independent work.
