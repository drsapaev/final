# Recovery Branch Manifest

## Scope
- Built only from the existing recovery reports and current main as the source of truth.
- No merge/cherry-pick/rebase/reset/delete-branch was performed in this pass.
- Each row is concrete; alias clouds from the earlier inventory are not collapsed into family-only summaries.

| branch name | merge-base with main | unique commit count vs main | touched top-level areas | short purpose | status | confidence | final recommendation |
|---|---|---|---|---|---|---|---|
| `dependabot/github_actions/actions/checkout-6` | `2539d522` | 1 | .github | GitHub Actions checkout bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `dependabot/github_actions/actions/setup-node-6` | `95dc355d` | 1 | .github | GitHub Actions setup-node bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `dependabot/github_actions/actions/setup-python-6` | `8d28b851` | 1 | .github | GitHub Actions setup-python bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `origin/dependabot/github_actions/actions/upload-artifact-7` | `bad472fe` | 1 | .github | GitHub Actions upload-artifact bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `origin/dependabot/github_actions/docker/build-push-action-7` | `bad472fe` | 1 | .github | GitHub Actions build-push-action bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `origin/dependabot/pip/backend/alembic-gte-1.13-and-lt-1.19` | `bad472fe` | 1 | backend | Backend Alembic requirement bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `origin/dependabot/pip/backend/fastapi-gte-0.121-and-lt-0.136` | `bad472fe` | 1 | backend | Backend FastAPI requirement bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `origin/dependabot/pip/backend/pydantic-gte-2.7-and-lt-2.13` | `bad472fe` | 1 | backend | Backend Pydantic requirement bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `origin/dependabot/pip/backend/uvicorn-standard--gte-0.29-and-lt-0.43` | `bad472fe` | 1 | backend | Backend Uvicorn requirement bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `origin/dependabot/pip/backend/redis-gte-5.0-and-lt-8.0` | `bad472fe` | 1 | backend | Backend Redis requirement bump | stale but valuable idea | HIGH_CONFIDENCE | cherry-pick candidate |
| `origin/codex/analyze-notification-function-in-panels` | `287db3db` | 3 | docs, frontend | Notification adapter precursor for admin/cashier panels | partially in main | HIGH_CONFIDENCE | defer |
| `codex/startup-operator-first-hardening` | `71163bde` | 42 | .ai-factory, .ai-factory.json, .codex, .github, .gitignore, backend, docs, frontend, ops, PLAN.md, README.md | Legacy cleanup and startup hardening sweep | dangerous to merge blindly | HIGH_CONFIDENCE | keep as reference |
| `codex/w2a-service-repository-initial` | `71163bde` | 2 | .ai-factory, backend, docs | Service/repository refactor for catalog handlers | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/w2a-service-repository-slice-012` | `71163bde` | 3 | .ai-factory, backend, docs | Service/repository refactor for read-only visit handlers | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/w2a-service-repository-slice-013` | `71163bde` | 4 | .ai-factory, backend, docs | Service/repository refactor for safe write visit handlers | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/w2a-human-review-pass` | `71163bde` | 5 | .ai-factory, backend, docs | Human review analysis for wave 2a | docs/evidence only | HIGH_CONFIDENCE | keep as reference |
| `codex/w2c-queue-architecture` | `71163bde` | 6 | .ai-factory, backend, docs | Wave 2c queue architecture baseline | docs/evidence only | HIGH_CONFIDENCE | keep as reference |
| `codex/w2c-execution-phase1` | `71163bde` | 7 | .ai-factory, backend, docs | Wave 2c phase 1 read boundaries | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/w2c-confirmation-boundary-migration` | `71163bde` | 19 | .ai-factory, backend, docs | Confirmation flow migration to allocation boundary | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/w2c-registrar-batch-boundary-migration` | `71163bde` | 23 | .ai-factory, backend, docs | Registrar batch migration to boundary layer | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/w2c-registrar-wizard-duplicate-fix` | `71163bde` | 26 | .ai-factory, backend, docs | Registrar wizard duplicate gate tightening | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/w2c-wizard-boundary-migration` | `71163bde` | 32 | .ai-factory, backend, docs | Wizard seam migration to boundary layer | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/w2c-broader-registrar-followup` | `71163bde` | 33 | .ai-factory, backend, docs | Follow-up doc for registrar allocator paths | docs/evidence only | HIGH_CONFIDENCE | keep as reference |
| `codex/w2c-high-risk-review` | `71163bde` | 15 | .ai-factory, backend, docs | High-risk queue allocator review notes | docs/evidence only | HIGH_CONFIDENCE | keep as reference |
| `codex/w2c-numbering-review` | `71163bde` | 11 | .ai-factory, backend, docs | Queue numbering policy review notes | docs/evidence only | HIGH_CONFIDENCE | keep as reference |
| `codex/w2c-confirmation-contract-review` | `71163bde` | 17 | .ai-factory, backend, docs | Confirmation queue contract review notes | docs/evidence only | HIGH_CONFIDENCE | keep as reference |
| `codex/post-w2c-board-state-adapter-skeleton` | `71163bde` | 39 | .ai-factory, backend, docs | Board state adapter skeleton for queue replacement | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/post-w2c-queues-stats-replacement` | `71163bde` | 37 | .ai-factory, backend, docs | Queues stats replacement with SSOT read model | stale but valuable idea | HIGH_CONFIDENCE | reimplement-from-main candidate |
| `codex/post-w2c-queues-stats-parity-harness` | `71163bde` | 36 | .ai-factory, backend, docs | Queues stats parity harness | stale but valuable idea | HIGH_CONFIDENCE | manual-port candidate |
| `codex/emr-v2-deprecation` | `88756b4c` | 0 | none | EMR v2 deprecation checkpoint | fully in main | HIGH_CONFIDENCE | defer |
| `codex/fix-ci-lab-bootstrap` | `296dacdf` | 0 | none | EMR template parity CI fix | fully in main | HIGH_CONFIDENCE | defer |
| `codex/lab-workflow-release` | `287db3db` | 0 | none | Laboratory panel workflow release | fully in main | HIGH_CONFIDENCE | defer |
| `codex/landing-factory-seed` | `c939269a` | 0 | none | Local-first acceptance seed | fully in main | HIGH_CONFIDENCE | defer |
| `codex/w15-docs-normalization-risk-claims` | `32e7ee04` | 0 | none | w15 checkpoint branch | fully in main | HIGH_CONFIDENCE | defer |
| `codex/w15-frontend-ci-blocker-fix` | `32e7ee04` | 0 | none | w15 checkpoint branch | fully in main | HIGH_CONFIDENCE | defer |
| `codex/w15-security-slice-a-frontend-deps` | `32e7ee04` | 0 | none | w15 checkpoint branch | fully in main | HIGH_CONFIDENCE | defer |
| `codex/w15-security-slice-b-bandit` | `32e7ee04` | 0 | none | w15 checkpoint branch | fully in main | HIGH_CONFIDENCE | defer |
| `codex/w15-stabilize-role-routing` | `32e7ee04` | 0 | none | w15 checkpoint branch | fully in main | HIGH_CONFIDENCE | defer |
| `codex/w175-gate-readiness` | `32e7ee04` | 0 | none | w175 checkpoint branch | fully in main | HIGH_CONFIDENCE | defer |
| `codex/w19-gate-blockers` | `32e7ee04` | 0 | none | w19 checkpoint branch | fully in main | HIGH_CONFIDENCE | defer |
| `codex/w195-gate-recheck` | `32e7ee04` | 0 | none | w195 checkpoint branch | fully in main | HIGH_CONFIDENCE | defer |
| `123` | `937c81db` | 2 | .claude, .cursor, .gitattributes, backend | Legacy admin/macOS snapshot with legacy queue file churn | obsolete | HIGH_CONFIDENCE | drop |
| `feat/macos-ui-refactor` | `bfde33f8` | 1 | backend | Binary database snapshot branch | obsolete | HIGH_CONFIDENCE | drop |

## Notes
- The manifest deliberately keeps the branch rows concrete and branch-specific instead of collapsing them into broad families.
- The dependabot rows are the only current safe cherry-pick candidates.
- The w2a / w2c / post-w2c branches are stale ideas that should be adapted from current main, not merged wholesale.
- The fully-in-main checkpoint branches remain listed for traceability, but their recovery action is defer.
