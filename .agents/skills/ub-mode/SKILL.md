---
name: ub-mode
description: Use when investigating or fixing a bug and an evidence-based reproduction and verification workflow would help. This is an optional, automatically discoverable pilot that can also be explicitly invoked; it is not required for every bugfix.
---

# Bugfix evidence pilot

Use this skill to make the evidence for a bugfix clear and proportionate to its risk. It is a voluntary pilot, not a requirement for every bugfix. Follow [AGENTS.md](../../../AGENTS.md), its required gates, canonical ownership, privacy rules, worktree and PR procedures, and applicable domain-specific skills. This skill grants no additional permissions and does not replace those controls.

## Workflow

1. Describe the observed symptom and expected behavior without patient data, secrets, or sensitive inputs and outputs. Inspect the canonical source and focused tests.
2. Before changing behavior, safely reproduce the defect when feasible. Prefer a focused behavior test and observe **RED** for the expected reason, not an unrelated setup or assertion failure. Record the command or reproducible steps and the observed outcome.
3. Identify the root cause and the evidence supporting it. If the cause is not established, label it a hypothesis and state the uncertainty. If the evidence cannot distinguish consequential competing causes or justify a specific change, defer the behavior change and report what safe evidence is needed.
4. Make the smallest appropriate fix. Repeat the same scenario and record **GREEN** and the actual result. Check affected neighboring invariants and the authorized change scope.
5. If an automated RED is impractical or unsafe, explain why and use the best available safe, reproducible evidence, such as a controlled manual scenario or focused diagnostic. State its limitations. Never manufacture a failing test or claim the fix is verified when the available evidence is insufficient.

Use targeted mutation testing only when the risk, available tooling, and cost justify it; mutation scores are not proof of complete coverage. Do not weaken existing checks or access controls to obtain a passing result.

## Evidence in the task report

Use the existing task report and, when a PR is part of the assignment, its Validation section. Include concise, actual results for:

Keep the repository's required report and PR headings intact. Place this evidence under the existing headings (for example, in Validation); do not replace or rename them.

- **RED or alternative:** symptom, expected outcome, reproduction and observed failure; or why RED was unavailable and what evidence was used.
- **ROOT CAUSE:** source or contract evidence and confidence, distinguishing a hypothesis from a confirmed cause.
- **GREEN:** the repeated scenario and its outcome, or why it could not be verified.
- **REGRESSION:** checks of affected neighboring invariants and any limitations.
- **SCOPE:** relevant changed files and confirmation of scope and safety constraints, or any exceptions.

Report commands and results honestly, including failures and checks not run. Do not copy patient information, secrets, raw inputs or outputs into reports or a separate action log.

## Pilot observation

For 2–3 separately authorized real bugfixes where this skill is selected, record in the existing task evidence:

- RED or alternative evidence.
- Root cause and confidence.
- GREEN result and neighboring invariants checked.
- Approximate extra time, or `not measured` when unavailable.
- Review feedback, or `pending` when review has not happened.
- Whether a genuinely comparable historical baseline exists; otherwise say it is unavailable.

These cases assess feasibility and cost, not proof of a reduction in defects. Any broader mandatory policy requires a separate decision.
