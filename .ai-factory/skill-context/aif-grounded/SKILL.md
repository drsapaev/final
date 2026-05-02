# `aif-grounded` Context

Read `../common/SKILL.md` first.

## Project-Specific Notes

- Prefer repo files, command output, and explicitly provided docs over memory when answering.
- Treat ports, versions, runtime endpoints, migration state, and release status as changeable until verified in the current workspace.
- Ground clinic-stack claims in the current workspace docs and config files before stating them as fact.
- If the answer depends on live state that cannot be verified locally, return `INSUFFICIENT INFORMATION` instead of inferring.
- When a current project rule already exists in `../common/SKILL.md`, use it as the baseline and verify any deviation before reporting it.
