# Memory Probe Protocol

Purpose: provide a small, explicit canary for testing whether a fact was
intentionally persisted into repo-owned memory instead of being remembered only
from chat context.

This protocol is for memory-health checks, not product truth. Probe entries are
evidence records and must not override source code, tests, migrations,
`AGENTS.md`, `PROJECT_MEMORY.md`, or CI gates.

## Storage

Write memory probe entries to:

```text
.ai-factory/logs/memory-probes.md
```

Do not put ordinary probe entries in `AGENTS.md` or
`docs/devbrain/PROJECT_MEMORY.md`. Promote a probe lesson only when it becomes a
repeated durable routing or ownership fact.

## Trigger

Use this protocol when the user explicitly asks for a memory probe or says to
record a control phrase/fact.

Accepted forms:

- `memory probe: <control phrase or fact>`
- `record memory probe: <control phrase or fact>`
- `запиши memory probe: <control phrase or fact>`
- any direct instruction that says to write a control phrase/fact for memory
  testing

If the user does not provide a phrase/fact, create a concise factual probe about
the current task and mark it as agent-generated.

## Entry Format

Each entry in the ledger should include:

- date and timezone;
- source instruction;
- exact control phrase or fact;
- whether it was user-provided or agent-generated;
- expected retrieval answer;
- storage target;
- validation run;
- status.

Keep the entry short. A probe should be easy to quote back exactly.

## Safety Rules

- Do not record secrets, tokens, credentials, patient data, production data, or
  personally sensitive facts as probe material.
- Do not treat a probe as project policy.
- Do not silently rewrite a user-provided control phrase.
- If the phrase is unsafe to store, refuse the unsafe material and offer a safe
  synthetic probe instead.
- If trusted retrieval should find the probe later, run the DevBrain memory
  refresh flow after committing the memory change.

## Retrieval Test

When asked later for the active memory probe, the agent should read
`.ai-factory/logs/memory-probes.md` and answer from the ledger, not from chat
memory.

Expected answer shape:

```text
Active memory probe: "<exact control phrase or fact>"
Source: <user-provided | agent-generated>
Stored in: .ai-factory/logs/memory-probes.md
```
