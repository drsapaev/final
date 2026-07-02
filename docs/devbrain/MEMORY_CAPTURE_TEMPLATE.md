# DevBrain Memory Capture Template

Use this template before adding durable DevBrain memory. The goal is to turn a chat observation, PR lesson, audit result, or repeated routing failure into a small routed fact with evidence.

Do not paste raw chat history. Distill it first.

## Capture

- Date:
- Trigger task or PR:
- Source evidence:
- One-sentence fact:
- Confidence: high / medium / low
- Scope: repo-wide / domain-specific / task-specific
- Sensitive data or secrets present: no / yes, redact before storing

## Route

- Knowledge type:
- Memory target:
- Why this target:
- Reindex needed: yes / no
- Validation command:

## Routing Checklist

- [ ] One-off observation -> `.ai-factory/logs` or `.ai-factory/dossiers`.
- [ ] Repeated ownership fact -> `docs/devbrain/PROJECT_MEMORY.md`.
- [ ] Retrieval/index status -> `docs/devbrain/DEVBRAIN_STATUS.md`.
- [ ] Repeated gate misroute -> `ai/langgraph/scripts/agent_gate.py` plus an acceptance scenario.
- [ ] Durable agent behavior rule -> `AGENTS.md`.
- [ ] Graph-heavy source lookup need -> `ai/llamaindex/data/manifest.json` if the source is not indexed.
- [ ] Relationship/ownership retrieval need -> `ai/lightrag/data/manifest.json` or `priority_focus_sources`.
- [ ] Enforceable review behavior -> PR template, review gate script, or CI workflow.

## Promotion Questions

Answer these before editing durable memory:

1. Will this fact be useful again after the current task?
2. Is it an ownership, routing, validation, or safety fact rather than a one-time note?
3. Does source code, a test, a migration, or a route registry already provide the better canonical anchor?
4. Could this become stale quickly?
5. Does changing this memory require a retrieval refresh?

If the answer to the first two questions is no, keep the fact in a log or dossier instead of promoting it.

## Entry Draft

### Summary

Write one short paragraph.

### Canonical Anchors

- Source:
- First-touch file:
- Validation target:

### Stop Conditions

- Stop if:
- Do not touch:

### Evidence

- Command or PR:
- Result:

### Memory Update

- Target file:
- Reindex command:
- Follow-up:

## Do Not Store

- Secrets, tokens, credentials, production data, or patient data.
- Raw chat transcripts when a short fact is enough.
- Speculation without evidence.
- Temporary local paths unless the path is the actual repo contract.
- Personal workflow preference unless it is a durable repo rule.
