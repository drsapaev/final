# Recovery Branch Inventory

## Baseline
- `main` at `959d457b` is the product truth for this audit pass.
- No merge/cherry-pick/rebase/reset/delete-branch was performed in this pass.
- Evidence used: `git for-each-ref`, `git branch --merged`, `git branch --no-merged`, `git diff main...<branch>`, `git log -1`, current `docs/`, `.ai-factory/`, `backend/`, and `frontend/`.

## Executive Table
| Bucket | Meaning | Current contents |
|---|---|---|
| Recover now | Small isolated maintenance that can be safely applied | Dependabot refs only, if dependency hygiene is still in scope |
| Reimplement later | Valuable idea, stale branch | w2a, w2c, post-w2c, wip-jules, notifications precursor |
| Drop forever | Obsolete / unsafe / binary snapshot | `123`, `feat/macos-ui-refactor` |
| Docs only | Evidence or stale architecture notes | `codex/startup-operator-first-hardening`, `origin/codex/post-w2c-next-legacy-slice-review`, stale queue/notification docs |

## Recover Now
| branch | tip_sha | family | unique_files_vs_main | overlap_status | risk | recommended_action | confidence | evidence_refs |
|---|---|---|---|---|---|---|---|---|
| `dependabot/github_actions/actions/checkout-6` | `0aa2a466` | gha deps | 6 workflow files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...dependabot/github_actions/actions/checkout-6` |
| `dependabot/github_actions/actions/setup-node-6` | `65a6c7b4` | gha deps | 2 workflow files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...dependabot/github_actions/actions/setup-node-6` |
| `dependabot/github_actions/actions/setup-python-6` | `6a7039f8` | gha deps | 6 workflow files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...dependabot/github_actions/actions/setup-python-6` |
| `origin/dependabot/github_actions/actions/upload-artifact-7` | `5f29f4d3` | gha deps | 4 workflow files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...origin/dependabot/github_actions/actions/upload-artifact-7` |
| `origin/dependabot/github_actions/docker/build-push-action-7` | `bad65a9f` | gha deps | 1 workflow file | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...origin/dependabot/github_actions/docker/build-push-action-7` |
| `origin/dependabot/pip/backend/alembic-gte-1.13-and-lt-1.19` | `671b39ed` | backend deps | 2 requirement files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...origin/dependabot/pip/backend/alembic-gte-1.13-and-lt-1.19` |
| `origin/dependabot/pip/backend/fastapi-gte-0.121-and-lt-0.136` | `3391d9f2` | backend deps | 2 requirement files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...origin/dependabot/pip/backend/fastapi-gte-0.121-and-lt-0.136` |
| `origin/dependabot/pip/backend/pydantic-gte-2.7-and-lt-2.13` | `28e9344a` | backend deps | 2 requirement files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...origin/dependabot/pip/backend/pydantic-gte-2.7-and-lt-2.13` |
| `origin/dependabot/pip/backend/uvicorn-standard--gte-0.29-and-lt-0.43` | `52782459` | backend deps | 2 requirement files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...origin/dependabot/pip/backend/uvicorn-standard--gte-0.29-and-lt-0.43` |
| `origin/dependabot/pip/backend/redis-gte-5.0-and-lt-8.0` | `3722442d` | backend deps | 2 requirement files | `NOT_IN_MAIN` | low | `CHERRY_PICK_SPECIFIC_COMMITS` | HIGH_CONFIDENCE | `git diff main...origin/dependabot/pip/backend/redis-gte-5.0-and-lt-8.0` |

## Already In Main Or Zero Diff
| branch | tip_sha | family | unique_files_vs_main | overlap_status | risk | recommended_action | confidence | evidence_refs |
|---|---|---|---|---|---|---|---|---|
| `dependabot/github_actions/actions/upload-artifact-5` | `559a5c88` | gha deps | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...dependabot/github_actions/actions/upload-artifact-5` |
| `codex/emr-v2-deprecation` | `88756b4c` | emr v2 checkpoint | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/emr-v2-deprecation` |
| `codex/fix-ci-lab-bootstrap` | `296dacdf` | lab bootstrap parity | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/fix-ci-lab-bootstrap` |
| `codex/lab-workflow-release` | `287db3db` | lab workflow release | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/lab-workflow-release` |
| `codex/landing-factory-seed` | `c939269a` | landing factory seed | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/landing-factory-seed` |
| `codex/w15-docs-normalization-risk-claims` | `32e7ee04` | w15 checkpoint family | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/w15-docs-normalization-risk-claims` |
| `codex/w15-frontend-ci-blocker-fix` | `32e7ee04` | w15 checkpoint family | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/w15-frontend-ci-blocker-fix` |
| `codex/w15-security-slice-a-frontend-deps` | `32e7ee04` | w15 checkpoint family | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/w15-security-slice-a-frontend-deps` |
| `codex/w15-security-slice-b-bandit` | `32e7ee04` | w15 checkpoint family | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/w15-security-slice-b-bandit` |
| `codex/w15-stabilize-role-routing` | `32e7ee04` | w15 checkpoint family | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/w15-stabilize-role-routing` |
| `codex/w175-gate-readiness` | `32e7ee04` | w15 checkpoint family | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/w175-gate-readiness` |
| `codex/w19-gate-blockers` | `32e7ee04` | w15 checkpoint family | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/w19-gate-blockers` |
| `codex/w195-gate-recheck` | `32e7ee04` | w15 checkpoint family | 0 files | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | HIGH_CONFIDENCE | `git diff main...codex/w195-gate-recheck` |

## Reimplement / Docs Only / Drop
| branch | tip_sha | family | unique_files_vs_main | overlap_status | risk | recommended_action | confidence | evidence_refs |
|---|---|---|---|---|---|---|---|---|
| `origin/codex/analyze-notification-function-in-panels` | `2f77309e` | notifications precursor | 7 files: docs/reports + frontend adapter path | `PARTIALLY_IN_MAIN` | medium | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...origin/codex/analyze-notification-function-in-panels` |
| `codex/startup-operator-first-hardening` | `53cede99` | w2d hardening / cleanup | 1380 files: backend/docs/frontend/ops/workflows | `CONFLICTS_WITH_MAIN_DIRECTION` | high | `KEEP_AS_REFERENCE_ONLY` | HIGH_CONFIDENCE | `git diff main...origin/codex/startup-operator-first-hardening` |
| `codex/w2a-service-repository-initial` | `c560b079` | w2a service/repository refactor | 16 files | `PARTIALLY_IN_MAIN` | medium | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2a-service-repository-initial` |
| `codex/w2a-service-repository-slice-012` | `b691a0cc` | w2a service/repository refactor | 21 files | `PARTIALLY_IN_MAIN` | medium | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2a-service-repository-slice-012` |
| `codex/w2a-service-repository-slice-013` | `e54d145a` | w2a service/repository refactor | 25 files | `PARTIALLY_IN_MAIN` | medium | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2a-service-repository-slice-013` |
| `codex/w2a-human-review-pass` | `2cd8a3a7` | w2a human review analysis | 30 files | `PARTIALLY_IN_MAIN` | medium | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2a-human-review-pass` |
| `codex/w2c-queue-architecture` | `00a800e0` | w2c queue architecture baseline | 38 files | `PARTIALLY_IN_MAIN` | medium | `DOCS_ONLY` | HIGH_CONFIDENCE | `git diff main...codex/w2c-queue-architecture` |
| `codex/w2c-execution-phase1` | `9a13eaaa` | w2c phase 1 read boundaries | 59 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-execution-phase1` |
| `codex/w2c-phase1-slice` | `7e337bb8` | w2c phase 1 read boundaries | 63 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-phase1-slice` |
| `codex/w2c-phase1-slice-002` | `2a276887` | w2c phase 1 read boundaries | 67 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-phase1-slice-002` |
| `codex/w2c-phase1-slice-004` | `7670be77` | w2c phase 1 read boundaries | 70 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-phase1-slice-004` |
| `codex/w2c-confirmation-boundary-migration` | `82980ab6` | w2c confirmation migration | 133 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-confirmation-boundary-migration` |
| `codex/w2c-confirmation-characterization` | `fbf55d0e` | w2c confirmation characterization | 115 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-confirmation-characterization` |
| `codex/w2c-confirmation-reuse-fix` | `34806a41` | w2c confirmation reuse fix | 127 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-confirmation-reuse-fix` |
| `codex/w2c-registrar-batch-boundary-migration` | `799774be` | w2c registrar batch migration | 156 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-registrar-batch-boundary-migration` |
| `codex/w2c-registrar-batch-create-fix` | `05eed531` | w2c registrar batch create fix | 225 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-registrar-batch-create-fix` |
| `codex/w2c-registrar-wizard-duplicate-fix` | `9f35c887` | w2c registrar wizard duplicate fix | 173 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-registrar-wizard-duplicate-fix` |
| `codex/w2c-safe-caller-migration` | `5cce9eff` | w2c safe caller migration | 100 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-safe-caller-migration` |
| `codex/w2c-wizard-boundary-migration` | `27096df6` | w2c wizard boundary migration | 208 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/w2c-wizard-boundary-migration` |
| `codex/post-w2c-board-state-adapter-skeleton` | `9341c49b` | post-w2c board-state adapter cluster | 249 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/post-w2c-board-state-adapter-skeleton` |
| `codex/post-w2c-board-state-prep` | `e5407a2c` | post-w2c board-state prep | 243 files | `PARTIALLY_IN_MAIN` | medium | `DOCS_ONLY` | HIGH_CONFIDENCE | `git diff main...codex/post-w2c-board-state-prep` |
| `codex/post-w2c-queues-stats-replacement` | `b2933e53` | post-w2c queues stats replacement | 237 files | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT_FROM_CURRENT_MAIN` | HIGH_CONFIDENCE | `git diff main...codex/post-w2c-queues-stats-replacement` |
| `codex/post-w2c-queues-stats-parity-harness` | `6d9b5e64` | post-w2c parity harness | 231 files | `PARTIALLY_IN_MAIN` | medium | `MANUAL_PORT_FROM_BRANCH` | HIGH_CONFIDENCE | `git diff main...codex/post-w2c-queues-stats-parity-harness` |
| `origin/codex/post-w2c-next-legacy-slice-review` | `07eef858` | post-w2c legacy slice review | 827 files | `CONFLICTS_WITH_MAIN_DIRECTION` | medium | `DOCS_ONLY` | HIGH_CONFIDENCE | `git diff main...origin/codex/post-w2c-next-legacy-slice-review` |
| `wip-jules-2025-12-19T16-08-26-129Z` | `8eaf2e66` | wip-jules handover | 303 files | `UNCLEAR_REQUIRES_DEEPER_REVIEW` | high | `KEEP_AS_REFERENCE_ONLY` | MEDIUM_CONFIDENCE | `git diff main...wip-jules-2025-12-19T16-08-26-129Z` |
| `wip-jules-2026-01-17T12-46-12-360Z` | `ce7f7f7a` | wip-jules user CRUD / env config | 543 files | `UNCLEAR_REQUIRES_DEEPER_REVIEW` | high | `KEEP_AS_REFERENCE_ONLY` | MEDIUM_CONFIDENCE | `git diff main...wip-jules-2026-01-17T12-46-12-360Z` |
| `123` | `99277d6a` | legacy admin/macOS snapshot | 4 files | `CONFLICTS_WITH_MAIN_DIRECTION` | high | `DROP` | HIGH_CONFIDENCE | `git diff main...123` |
| `feat/macos-ui-refactor` | `e2bb65e9` | binary db snapshot | 1 file (`backend/clinic.db`) | `CONFLICTS_WITH_MAIN_DIRECTION` | high | `DROP` | HIGH_CONFIDENCE | `git diff main...feat/macos-ui-refactor` |

## Notes
- Alias clouds such as the `9341c49b`, `05eed531`, and `w15` families are compressed intentionally. The decision applies to each alias unless a narrower sub-audit proves otherwise.
- The notification precursor branch is not a merge candidate; current main already has the better notifications architecture.
