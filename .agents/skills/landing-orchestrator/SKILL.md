---
name: landing-orchestrator
description: Inspect and manage an AI Landing Factory run, refresh run-manifest.json, and move the run through intake, build, audit, and release. Use when coordinating multiple landing skills or checking readiness between stages.
---

# Landing Orchestrator

This skill is the control plane for landing runs. It should prefer the helper script over manual manifest editing.

## Primary Commands

- `python scripts/landing_factory/run_pipeline.py status <run-dir>`
- `python scripts/landing_factory/run_pipeline.py sync <run-dir> --auto-advance`
- `python scripts/landing_factory/run_pipeline.py sync <run-dir> --aggregate-scorecard`
- `python scripts/landing_factory/run_pipeline.py advance <run-dir> --to build`

## Stage Model

- `intake`: owned by `landing-intake`
- `build`: owned by `landing-strategy`, `landing-copy`, `landing-design-system`, `landing-ui-build`
- `audit`: owned by the audit swarm
- `release`: owned by `landing-release` with scorecard evidence

## Workflow

1. Run `status` first to inspect the current manifest.
2. If audits changed, run `sync --aggregate-scorecard`.
3. If the current stage is ready, use `sync --auto-advance` or `advance --to <stage>`.
4. Keep the run grounded in artifacts, not chat memory.

## What It Adds

- per-stage `skill_checks`
- one `recommended_skill` with a concrete reason
- release-time `repair_queue` when scorecard gates fail or remain pending

## Guardrails

- do not advance stages while required artifacts are still missing unless the user explicitly wants an override
- prefer `advance --force` only for deliberate rollback or manual operator intervention
- treat `run-manifest.json` as the operational truth for the current landing run
