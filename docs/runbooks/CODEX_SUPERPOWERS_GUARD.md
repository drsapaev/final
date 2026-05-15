# Codex Superpowers Guard

This runbook is the repository-owned source of truth for using a Superpowers-style workflow guard in this project.

It does not vendor, install, or configure the external Superpowers plugin. If the plugin is available in Codex, use it as an optional manual guard. If it is not available, follow this runbook and `AGENTS.md`.

## Local SSOT

Use these sources in order:

1. `AGENTS.md`
2. This runbook
3. `.agents/skills/*/SKILL.md` for task-specific skills
4. `ai/langgraph/scripts/agent_gate.py` when `AGENTS.md` says a gate is required
5. The canonical source, tests, routes, migrations, contracts, or runbooks found for the task

Do not treat chat history, plugin marketing pages, broad overview docs, or generated reports as stronger authority than the files above.

## What Superpowers Means Here

In this repository, "Superpowers" means a disciplined execution loop:

1. Clarify the task mode and risk.
2. Locate canonical anchors before editing.
3. Define the first safe patch slice.
4. Use the relevant skill or local gate when needed.
5. Make a small patch.
6. Run the narrowest useful validation.
7. Report evidence, remaining risk, and follow-ups.

This is a workflow policy, not application code.

## What Is Not Repo-Owned

The following are intentionally not part of this repository:

- External Superpowers plugin source code
- User-level Codex plugin installation state
- Global files under `$HOME/.codex`
- Global files under `$HOME/.agents`
- Marketplace metadata or plugin cache directories

Do not add those files to this repository. Do not modify shared user-level Codex settings unless the user explicitly asks for local machine setup.

## Required Agent Behavior

When a prompt says `Use Superpowers workflow guard`, do this before editing:

```text
Execution mode
selected mode:
reason:
risky domain: yes/no
root cause known: yes/no
scope expectation: single-file / narrow / multi-file
command:
actual command to run
or not needed for direct execute

Initial boundaries
canonical anchor:
first-touch files:
validation target:
stop condition to watch first:
```

Then follow the execution mode rules in `AGENTS.md`.

For `direct_execute`, the local gate is not required, but the boundaries still are.

For `gate` or `gate_known_root_cause`, run:

```powershell
cd C:\final\ai\langgraph
python scripts\agent_gate.py "<task>"
```

or:

```powershell
cd C:\final\ai\langgraph
python scripts\agent_gate.py "<task>" --known-root-cause "<relative/path.py>"
```

If the gate cannot run, stop and report instead of improvising.

## Skill Routing

Use `.agents/skills` as the repo-owned skill directory.

Project-specific skills take precedence over generic skills:

- Clinic UI work: `clinic-frontend-design` first.
- GitHub Actions work: `github-actions-docs` for syntax/security and `gh-fix-ci` for failing checks.
- Security work: `code-security` first, then `semgrep` when a concrete scan or rule is needed.
- Frontend validation: `javascript-testing-patterns`, `vitest`, `webapp-testing`, and `playwright-best-practices` as relevant.

Do not use a generic frontend design workflow to override clinic readability, role clarity, accessibility, or the existing design system.

## Safe Patch Contract

Before the first edit, name:

- Canonical anchors
- Reference-only files
- First-touch files
- Narrow validation target
- Stop condition

During implementation:

- Keep the first patch small.
- Touch only the allowed first-touch files.
- Avoid opportunistic cleanup.
- Do not expand scope silently.
- Preserve dirty worktree changes you did not create.
- Do not weaken CI, permissions, RBAC, contracts, or production safety gates.

## Validation Contract

Prefer the narrowest validation that can prove the patch:

- Docs-only: markdown/static link checks when available, `git diff --check`, and PR quality gates.
- GitHub Actions: YAML parse, stale-reference search, `actionlint` if available, and PR checks.
- Frontend: lint/unit/build/browser checks scoped to touched files or affected flows.
- Backend: targeted unit/integration tests, migration checks, and contract/parity checks when relevant.
- Security: static checks and focused exploit/regression proof when changing sensitive code.

If a requested validation tool is not installed locally, say that explicitly and use the best available local substitute.

## PR Evidence

Every non-trivial PR should include:

- Summary
- Files changed
- Why the scope is safe
- Validation commands and results
- What was intentionally not changed
- Remaining risks
- Follow-ups

For runtime-risk PRs, also fill the required project PR review fields for contract impact, RBAC, notification/realtime, frontend resilience, and scope gate.

## Acceptance Check

This local SSOT is active when:

- `AGENTS.md` points to this runbook.
- Agents can follow the guard even if the external Superpowers plugin is unavailable.
- Runtime code is not changed by the guard itself.
- PRs using the guard show a small patch, explicit validation, and clear residual risk.
