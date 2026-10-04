# DevBrain memory benchmark

This is an explicit, local measurement tool. It is not imported by memory
startup, a client adapter, or CI. `validate` never launches a model. A model
run requires the `pilot` or `expand` action, the exact `gpt-6-luna` slug, and
`--confirm-model-runs`.
Model runs are supported only on native Windows, where the repository's
PowerShell launchers and file-memory locking contract are defined. Offline
validation remains portable.

## Variants and scenarios

- `legacy_manual` uses the tracked AGENTS.md, Project Memory, status, and
  routing documents from commit `04220b575f463af4da4d9f4381ca74275f8eb513`.
  Its capture and fresh recall use the pre-PR3 manual `.ai-factory/logs` note
  workflow.
- `automatic_helper` uses the current post-PR3 bootstrap and the local memory
  helper. Its experimental curated catalog is empty so the task answer cannot
  be recalled from already-known curated facts; the session must save a local
  source-backed fact and checkpoint.
- Both variants get the same current backend/frontend source and test files for
  the scenario. Their product source/test fingerprint is checked before a
  run, and the CLI works only in a disposable scratch Git repository.
- The pilot is `api_ws_origin`: four independent ephemeral Codex sessions,
  capture and fresh recall for each variant. `expand` requires a completed,
  passing pilot and adds the Registrar and Telegram scenarios, for a hard total
  limit of 12 sessions.

Each session uses `codex exec --ephemeral --json --sandbox workspace-write`,
the exact requested model, and no resume/fork command. The automatic variant
adds only that scratch repository's `.git/devbrain-memory/v1` as an additional
writable directory. The runner never uses the sandbox bypass option. It does
not pass source checkout paths to the model; only allowlisted source snapshots
are copied into disposable workspaces.

## Run

From the repository root, validate offline:

    .\scripts\run_python.ps1 -PythonArgs @('scripts/devbrain_benchmark/runner.py','validate')

Run the bounded four-session pilot only when ready to spend model usage:

    .\scripts\run_python.ps1 -PythonArgs @('scripts/devbrain_benchmark/runner.py','pilot','--model','gpt-6-luna','--confirm-model-runs')

After reviewing a successful pilot artifact, explicitly add the two remaining
scenarios:

    .\scripts\run_python.ps1 -PythonArgs @('scripts/devbrain_benchmark/runner.py','expand','--model','gpt-6-luna','--confirm-model-runs','--results','.scratch/devbrain_benchmark/<pilot-result>.json')

Result files and disposable workspaces stay under
`.scratch/devbrain_benchmark/` in the calling worktree. They are not committed
or written to production artifacts. Do not copy raw transcripts or JSONL
payloads into the result; the runner retains only usage counters, elapsed time,
output bytes, session IDs, helper-call counts, assertion booleans, and blocker
codes.

## Metrics and stop behavior

For every capture and recall session, counters are read only from the
`turn.completed.usage` JSONL event. Input, cached input, and output tokens are
summed separately for the full two-session cycle. If any required counter is
missing, the result says `USAGE_UNAVAILABLE` and contains `null`; bytes are
never converted to token estimates. Elapsed time is measured around the CLI
process. Output bytes are the captured JSONL stdout size. No subscription cost
is calculated.

The first session is the wire-shape pilot. If the model is unavailable, the
sandbox blocks the designated scratch write, a counter is missing, a quality
assertion fails, or any write escapes the disposable workspace, the runner
stops and records a bounded blocker. It does not substitute a model, retry
through a broader sandbox, or expand automatically. Result summaries compare
the median per-scenario full-cycle input reduction and elapsed-time change.
The preliminary economy threshold is at least 20% lower median input tokens,
with no quality loss and no more than 10% median elapsed-time increase.

## Schemas

- `scenario.schema.json` describes the fixed, source-anchored cases and their
  private evaluator assertions.
- `response.schema.json` constrains each model's structured output.
- `result.schema.json` describes the bounded result artifact. Raw model output
  and source text are deliberately omitted.

The Python runner validates its supported fields with the standard library;
the schemas are also machine-readable for external validators. No new Python
package is required.
