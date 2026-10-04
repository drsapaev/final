# DevBrain Status

Operational status for repository memory and guardrail layers. Verify this file
against the current checkout before relying on optional retrieval artifacts.

## Current status

| Layer | Status | Operational meaning |
| --- | --- | --- |
| `AGENTS.md`, runbooks, skills | active | Portable operating rules and domain guidance read directly by agents. |
| `docs/devbrain/PROJECT_MEMORY.md` | active | Compact, repository-tracked project memory. |
| `scripts/devbrain_memory.py` | local memory tool available | Checkpoints and local knowledge are stored under this clone's Git common directory and shared by its linked worktrees. `AGENTS.md` defines the agent-called start/recall/capture lifecycle; there are no client event hooks. |
| `docs/devbrain/memory/curated.json` | tracked portable memory | Reviewed repo facts are recalled with pinned source hashes; stale or dirty sources are not current assertions. |
| Codex adapter | configured; runtime unverified | Repo instructions are present; a new-session call/recall check remains pending. |
| Claude adapter | configured; runtime unverified | Claude CLI was not found on PATH; no installation was attempted. |
| Cursor adapter | configured; runtime unverified | Cursor application CLI is present, but a fresh Agent chat call/recall check remains pending. |
| ZCode | configured via root `AGENTS.md`; runtime unverified | [ZCode reads workspace `AGENTS.md` directly](https://zcode.z.ai/en/docs/agents), but its CLI was not found on PATH here. Built-in Project Memory is a separate optional feature; DevBrain does not enable it. |
| `ai/langgraph/scripts/agent_gate.py` | active | Deterministic execution guard for tasks routed through gate modes. |
| LlamaIndex | dormant | Legacy local lexical retrieval. Do not run by default. |
| LightRAG | dormant | Legacy relationship retrieval. Do not run by default. |

ADR-0007 is the policy source for dormant LlamaIndex and LightRAG status. Their
source directories and launchers may exist while generated indexes are absent
or stale. Filesystem presence and old status text do not activate them.

## Local memory commands

Use the shared local memory helper through its PowerShell launcher:

```powershell
.\scripts\run_devbrain_memory.ps1 -Action Status
.\scripts\run_devbrain_memory.ps1 -Action Begin -Query "short task summary"
.\scripts\run_devbrain_memory.ps1 -Action Recall -TaskId "<uuid>"
.\scripts\run_devbrain_memory.ps1 -Action Capture -InputFile ".scratch\devbrain-capture.json"
```

The store is local to one clone and shared by that clone's Git worktrees. It is
not synchronized to other clones or machines. Status reports store health and
counts without dumping saved content. Agent calls are instruction-driven, not
client hooks or background conversation analysis.

## Guardrail acceptance

Run the read-only acceptance checker to exercise deterministic gate scenarios:

```powershell
.\scripts\devbrain_acceptance.ps1
```

This checks routing behavior. It does not prove product behavior or activate
legacy retrieval.

## Regression matrix

The default matrix checks portable memory, the local memory helper, and
guardrail behavior. Legacy retrieval probes and freshness checks are an
intentional skip unless explicitly requested:

```powershell
.\scripts\devbrain_regression_matrix.ps1
.\scripts\devbrain_regression_matrix.ps1 -IncludeRetrieval
```

`-IncludeRetrieval` reads existing index metadata and may query only when the
corresponding generated index is already present. Missing indexes are reported
without being created. Freshness comes from the artifacts' own commit metadata,
not from this historical status document.

Markdown coverage is likewise opt-in:

```powershell
.\scripts\devbrain_markdown_index_coverage.ps1 -IncludeRetrieval
```

## Refresh behavior

The default refresh checks local filesystem memory and the portable regression
matrix. It does not ingest, query, export, or update retrieval artifacts:

```powershell
.\scripts\devbrain_refresh_memory.ps1
```

Only an explicit request refreshes legacy retrieval:

```powershell
.\scripts\devbrain_refresh_memory.ps1 -RefreshRetrieval
```

That option calls Python entry points through `scripts/run_python.ps1` without
the legacy `--update-status` flag. Generated retrieval output stays in ignored
local storage. A smoke or acceptance result is historical evidence for that
run; it does not change ADR-0007 or this durable dormant policy.

## Historical retrieval evidence

The following values are dated observations from 2026-05-26, not current
readiness claims:

| Layer | Recorded commit | Last recorded verification | Historical result |
| --- | --- | --- | --- |
| LlamaIndex | `8356203b8323970870931901e17a6bcfd67d3874` | `2026-05-26T18:28:52+00:00` | 1,627 documents; simple locate smoke passed in no-key fallback mode. |
| LightRAG | `8356203b8323970870931901e17a6bcfd67d3874` | `2026-05-26T18:28:55+00:00` | 1,513 documents, 12 concepts, 6,837 edges; historical acceptance reported pass. |

These historical counts and acceptance notes do not establish present artifact
availability, freshness, or usefulness. Re-evaluation requires an explicit
request and current artifact metadata.

## Known limitations

- Local automatic memory is per clone; it does not synchronize independent
  clones or computers.
- Memory records are advisory. Source, tests, migrations, and repository rules
  remain authoritative.
- The model still performs reasoning and execution; DevBrain is not an
  autonomous production developer.
- Legacy retrieval artifacts can be missing or stale while the project status
  remains correctly dormant.
