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
