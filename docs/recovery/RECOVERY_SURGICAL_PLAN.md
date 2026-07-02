# Surgical Recovery Plan

## Goal
Reconstruct a contamination-free recovery-only PR from exact `origin/main` that contains only:
- recovery docs import / reconciliation
- validated dependency / CI recovery changes
- recovery execution / validation / completion docs

## Non-goals
- No runtime feature work
- No historical branch merge
- No broad cherry-pick of mixed-scope commits
- No touch to local `main`

## Allowed reconstruction method
1. Start from exact `origin/main` SHA `22da512420a605f94b419e8e5994818e1e88d2fa`.
2. Import only whitelisted files.
3. For pure dependency/workflow commits, reapply only the approved file slice.
4. For mixed docs commits, manually port only approved docs files.
5. After each import, verify `git diff --name-only origin/main...HEAD` stays within whitelist.

## Hard gate
If any forbidden path appears in the diff, stop and remove it before continuing.

## Validation plan
- `git diff --check`
- workflow YAML parse
- backend import smoke if dependency constraints change backend packaging
- targeted pytest for the validated dependency / notification safety slice
- forbidden artifact scan

## Completion criteria
- Only whitelist-approved files changed
- No runtime files outside approved docs / workflow / dependency scope
- Surgical branch ready for PR creation
