# Compact repository relationship analysis

Use this path when `AGENTS.md` routes a complex repository task to Archify and
the user needs analysis rather than a rendered diagram. The agent traces
relationships from source; the Archify CLI does not discover dependencies.

## Reuse before reading

Follow the task-memory lifecycle in `AGENTS.md`: continue with the trusted
task's exact ID, or use the already-started task's recall. Reuse matching
repo-scoped facts only as leads. Check their anchors and current callers,
consumers, or writers where those can affect this task. A matching hash
confirms that file's bytes, not that an old relationship map is complete.
Other task checkpoints never select or replace the current task.

## Trace the smallest useful slice

1. State the relationship the decision depends on: for example, who calls a
   behavior, which component owns a write, where a value is read, or which
   contract crosses a boundary.
2. Start at the relevant entry point, registration, contract, or source anchor.
   Follow only the callers, callees, reads, writes, and focused tests needed to
   answer that question. Use current source and tests as authority; notes,
   package descriptions, labels, and old diagrams are navigation aids only.
3. For each relationship that affects the plan, identify its source path and
   relevant symbol or line. Distinguish observed behavior from inference; leave
   unresolved edges explicit. Do not scan unrelated areas to make the map look
   complete.
4. Stop when the decision-relevant relationships have source support and
   remaining unknowns cannot change the plan or allowed scope. If ownership,
   contracts, a gate, or a stop condition remains unclear, follow `AGENTS.md`
   and stop before editing.

## Keep and report only reusable evidence

Keep the working summary to a few concise bullets: relationship chain, owner of
the relevant read/write, supporting sources/tests, and any unresolved question
or next source to inspect. Do not copy full files, conversations, tool output,
or produce an HTML/JSON diagram in this path.

At normal task checkpoints, capture only durable facts that will help another
task. Use source anchors for committed evidence; keep dirty-worktree findings
worktree-scoped and never promote them as shared contracts. Keep task-specific
progress under its exact task ID. Respect the memory helper's record and output
limits. Never store PHI/PII, credentials, or large source excerpts. Memory stays
advisory and cannot authorize changes, override gates, or prove runtime health.

Create a diagram only when the user requests one or a visual view materially
helps communicate the relationships. Then switch to the normal authoring and
`finalize` workflow in `SKILL.md`.
