# AI Factory Skills Inventory

Date: 2026-03-06

## Scope Rule

This inventory covers the skills that are relevant to the AI Factory plus OpenHands foundation prepared in this setup.

No new external third-party skills were installed during this work.

Pre-existing broad skills remain on disk, but they are not part of the default execution set unless explicitly selected for a bounded task.

## Core Control-Plane Skills

| Skill | Source | Purpose | Trust notes | Custom/local |
|---|---|---|---|---|
| `aif` | pre-existing local AI Factory skill | Existing project analysis and AI Factory baseline management | Local repo skill; used as control-plane context, not executor authority | yes |
| `aif-docs` | pre-existing local AI Factory skill | Documentation generation and maintenance guidance | Local repo skill; used to shape docs output only | yes |
| `aif-skill-generator` | pre-existing local AI Factory skill | Generate and validate narrow local skills | Local repo skill; also used for security-scan workflow | yes |

## External Reference Skills Kept In Scope

These were already installed before this setup. They are reference aids only, not authority to bypass repo guardrails.

| Skill | Source | Purpose in this repo | Trust notes | Custom/local |
|---|---|---|---|---|
| `fastapi-templates` | `.agents/skills` from `wshobson/agents` | Backend pattern reference for service/repository cleanup | Level 1 scan clean; use only as pattern reference | no |
| `github-actions-templates` | `.agents/skills` from `wshobson/agents` | CI workflow reference for narrow GitHub Actions fixes | Level 1 scan clean; human review still required for workflow edits | no |
| `python-testing-patterns` | `.agents/skills` from `wshobson/agents` | Reference for backend and integration test additions | Level 1 warnings only for `pip install` examples; manual review passed; reference-only | no |
| `vercel-react-best-practices` | `.agents/skills` from `vercel-labs/agent-skills` | Frontend performance and rendering guidance for bounded UI work | Level 1 warning only for `npm install` example; manual review passed; reference-only | no |
| `vite` | `.agents/skills` from `antfu/skills` | Vite-specific build/test config reference | Level 1 scan clean; reference-only | no |
| `vitest` | `.agents/skills` from `antfu/skills` | Vitest-specific test config reference | Level 1 scan clean; reference-only | no |
| `webapp-testing` | `.agents/skills` from `anthropics/skills` | Optional browser-testing reference for UI verification | Level 1 scan clean; use only when browser validation is actually needed | no |

## New Narrow Local Skills Added For This Foundation

| Skill | Source | Purpose | Trust notes | Custom/local |
|---|---|---|---|---|
| `repo-audit` | local custom | Repo and environment precheck before planning or execution | Authored in-repo, scan clean, bounded to inspection and reporting | yes |
| `docs-vs-code-verification` | local custom | Verify docs claims against code and tests | Authored in-repo, scan clean, prefers docs fixes over behavior changes | yes |
| `service-repository-refactor` | local custom | Bounded backend service/repository cleanup outside protected domains | Authored in-repo, scan clean, explicitly excludes protected modules by default | yes |
| `ci-cd-stabilization` | local custom | Narrow GitHub Actions stabilization workflow | Authored in-repo, scan clean, requires human review for workflow edits | yes |
| `auth-rbac-audit` | local custom | Audit auth and RBAC parity across code, tests, and docs | Authored in-repo, scan clean, protected-domain review required | yes |
| `frontend-backend-contract-audit` | local custom | Audit payload and route parity across UI and API layers | Authored in-repo, scan clean, contract drift oriented | yes |
| `queue-consistency-audit` | local custom | Audit queue system consistency without queue rewrites | Authored in-repo, scan clean, human review required for behavior changes | yes |
| `payment-hardening` | local custom | Audit or harden payments within strict boundaries | Authored in-repo, scan clean, no secret changes allowed | yes |
| `accessibility-polish` | local custom | Small a11y improvements outside protected flows | Authored in-repo, scan clean, bounded to non-protected UI surfaces | yes |
| `security-housekeeping` | local custom | Low-risk security cleanup and verification | Authored in-repo, scan clean, explicitly excludes secret rotation and deep rewrites | yes |
| `critical-flow-test-mapping` | local custom | Map critical flows to existing test coverage and gaps | Authored in-repo, scan clean, mapping-first skill | yes |
| `docs-cleanup` | local custom | Remove stale doc claims and improve doc clarity | Authored in-repo, scan clean, docs-first and evidence-driven | yes |

## Inventory Summary

- New external installs performed in this setup: `0`
- New local custom skills added: `12`
- Existing external reference skills kept in scope: `7`
- Default execution principle: use the narrowest relevant skill plus contract guardrails, not the broadest available skill set
