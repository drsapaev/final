# AI Landing Factory Runbook

This runbook describes the minimal operational flow for the landing-page pipeline scaffolded in this repository.

## Prerequisites

- landing run templates under `.ai-factory/landing/templates/`
- landing skills under `.agents/skills/landing-*`
- helper scripts:
  - `python scripts/landing_factory/scaffold_run.py`
  - `python scripts/landing_factory/aggregate_scorecard.py`
  - `python scripts/landing_factory/run_pipeline.py`

## 1. Create a Run

```bash
python scripts/landing_factory/scaffold_run.py --slug acme-product
```

This creates:

- `briefs/`
- `plans/`
- `design/`
- `content/`
- `audits/`
- `release/`

inside `.ai-factory/landing/runs/<timestamp>-acme-product/`.

## 2. Recommended Agent Order

1. `$landing-intake`
2. `$landing-strategy`
3. `$landing-copy`
4. `$landing-design-system`
5. `$landing-ui-build`
6. audit swarm in any safe order:
   - `$landing-design-audit`
   - `$landing-ux-audit`
   - `$landing-accessibility`
   - `$landing-seo`
   - `$landing-performance`
   - `$landing-visual-qa`
   - `$landing-conversion`
7. `$landing-release`
8. `$landing-orchestrator` whenever you need to inspect or move the run state

## 3. Artifact Ownership

- intake owns `briefs/*.json`
- strategy owns `plans/pipeline_plan.md`
- ui build owns `plans/build_status.json`
- copy owns `content/landing-copy.md`
- design system owns `design/*.json`
- release owns `release/*.md` and `release/qa-scorecard.json`

Audit agents should write only their own files under `audits/`.

## 4. Build and Validation Flow

Recommended execution sequence after implementation:

1. `npm run build`
2. run the local preview server
3. run Lighthouse against the preview URL
4. run Playwright smoke or conversion checks
5. run Axe or equivalent accessibility checks
6. update `release/qa-scorecard.json` results
7. aggregate:

```bash
python scripts/landing_factory/aggregate_scorecard.py .ai-factory/landing/runs/<run-id>
```

Refresh the manifest and move stages:

```bash
python scripts/landing_factory/run_pipeline.py sync .ai-factory/landing/runs/<run-id> --auto-advance --aggregate-scorecard
```

Inspect the current recommended skill and checklist:

```bash
python scripts/landing_factory/run_pipeline.py status .ai-factory/landing/runs/<run-id>
```

The manifest will keep:

- `skill_checks` for the active stage
- `recommended_skill` with a reason
- `repair_queue` on release when gates fail

## 5. Release Rules

- preview can be prepared automatically
- production requires explicit approval
- unresolved critical issues keep the run in failed status
- missing evidence keeps the run in pending status

## 6. First Iteration Scope

Keep the first real pipeline narrow:

- one landing at a time
- one primary audience
- one primary CTA
- preview-only release path

That gives a reliable loop before adding autonomous deploy behavior.
