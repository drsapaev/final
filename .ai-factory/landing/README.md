# AI Landing Factory Workspace

This folder stores reusable templates and run artifacts for the landing-page pipeline.

## Layout

- `templates/` contains starter artifacts copied into each new run.
- `runs/` contains timestamped landing runs created by `python scripts/landing_factory/scaffold_run.py`.

## Recommended Flow

1. Create a run:
   - `python scripts/landing_factory/scaffold_run.py --slug your-project`
2. Fill intake artifacts with `$landing-intake`.
3. Progress through strategy, copy, design system, UI build, and audits.
4. Aggregate the scorecard:
   - `python scripts/landing_factory/aggregate_scorecard.py .ai-factory/landing/runs/<run-id>`
5. Refresh or move stages with the control plane:
   - `python scripts/landing_factory/run_pipeline.py status .ai-factory/landing/runs/<run-id>`
   - `python scripts/landing_factory/run_pipeline.py sync .ai-factory/landing/runs/<run-id> --auto-advance --aggregate-scorecard`

The control plane writes:

- `stage_status.<stage>.skill_checks`
- `stage_status.<stage>.recommended_skill`
- `stage_status.release.repair_queue`

Actual release logic remains approval-gated. Preview and production decisions should be based on the generated audit artifacts, not chat-only summaries.
