---
name: archify
description: Use for complex repository analysis spanning call chains, ownership, state or persistence flows, or change impact when a wrong relationship could alter the plan, even without a diagram request. Also create repository-grounded architecture, workflow, sequence, data-flow, or lifecycle diagrams. Skip simple/local or already-evidenced work. Follow AGENTS.md; diagram checks establish artifact quality, not runtime health.
license: MIT
metadata:
  version: "3.0.1"
  author: tt-a1i
  based_on: Cocoon-AI/architecture-diagram-generator (MIT, v1.0)
---

# Archify

Use the compact source-backed path in [Agent analysis](references/agent-analysis.md) for complex relationship questions. It does not create an HTML diagram. Read [Diagram authoring](references/diagram-authoring.md) only for a requested or materially useful visual artifact; that reference routes to the relevant schemas and authoring details.

## Type router

| Type | Use for | Schema | Example |
|---|---|---|---|
| `architecture` | Components, services, cloud/security boundaries, infrastructure | `schemas/architecture.schema.json` | System descriptions, services, libraries, CLI repos: `examples/web-app.architecture.json`; deployment repos: `examples/production-deployment.architecture.json` |
| `workflow` | Processes, approval gates, tool calls, runbooks, CI/CD | `schemas/workflow.schema.json` | `examples/agent-tool-call.workflow.json` |
| `sequence` | API call chains, request lifecycles, async traces, returns | `schemas/sequence.schema.json` | `examples/cache-miss-request.sequence.json` |
| `dataflow` | Pipelines, ETL/ELT, lineage, governance, consumers | `schemas/dataflow.schema.json` | `examples/product-analytics.dataflow.json` |
| `lifecycle` | State/status transitions, retries, waiting and terminal states | `schemas/lifecycle.schema.json` | `examples/deployment-release.lifecycle.json` |

When the type is ambiguous, use `node bin/archify.mjs guide "<scenario>" --json`. Treat examples as structural references; derive repository facts from current source.
