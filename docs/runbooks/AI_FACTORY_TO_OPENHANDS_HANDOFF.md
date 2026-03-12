# AI Factory To OpenHands Handoff

Date: 2026-03-06

## Goal

Provide a simple, reviewable handoff from AI Factory planning to OpenHands execution without claiming direct integration that does not exist.

## Handoff Artifacts

Required:

- one execution contract JSON file in `.ai-factory/contracts/`
- one rendered handoff prompt from `ops/openhands/render-contract.ps1`

Optional:

- supporting issue link
- CI failure link
- local notes about missing credentials or blocked tests

## Flow

1. AI Factory inspects the repo and chooses the correct narrow skill.
2. AI Factory fills the matching contract template.
3. Human reviews:
   - scope include/exclude
   - protected paths
   - `max_files_changed`
   - `max_diff_lines`
   - mandatory review notes
4. The contract is rendered into `*.handoff.md`.
5. OpenHands is started locally with the repo mounted as `/workspace`.
6. The rendered prompt is pasted into OpenHands.
7. OpenHands executes only within the contract.
8. Human reviews the result and GitHub Actions arbitrate final quality.

## Contract Ownership

### AI Factory owns

- task type selection
- goals
- constraints
- protected-path exclusions
- must-run checks
- stop conditions
- required artifacts

### OpenHands owns

- bounded execution
- code edits inside approved scope
- local test runs inside approved scope
- explicit stop on escalation conditions

### Human owns

- approval before execution
- any override for protected domains
- final merge decision

## Current v1 Boundary

This repo now supports:

- contract templates
- a renderer that turns contract JSON into an executor-ready prompt
- a local OpenHands launcher wrapper

This repo does not yet support:

- AI Factory automatically opening an OpenHands session
- AI Factory programmatically feeding the contract into OpenHands
- automatic callback from OpenHands back into AI Factory memory

## Required Stop Rules During Handoff

OpenHands must stop and hand control back when:

- a protected path must be edited
- the file or diff budget will be exceeded
- required tests cannot run
- secrets or production credentials appear necessary
- the task drifts outside the declared contract

## Minimum Review Checklist

- contract file matches the actual task
- protected zones are either excluded or explicitly escalated
- must-run checks are realistic
- required artifacts are listed
- no claim of full automation is made in status notes
