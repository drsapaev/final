# Recovery Changeset Decisions

| change-set | overlap with main | risk | action | rationale |
|---|---|---|---|---|
| Dependabot gha/backend dependency refs | `NOT_IN_MAIN` | low | `CHERRY_PICK` | Small, isolated dependency maintenance with clear commit boundaries. |
| `origin/codex/analyze-notification-function-in-panels` | `PARTIALLY_IN_MAIN` | medium | `REIMPLEMENT` | Useful notification-adapter idea, but current main already has a better notify adapter path. |
| `codex/w2a-service-repository-*` | `PARTIALLY_IN_MAIN` | medium | `REIMPLEMENT` | Service-layer direction is useful, but the concrete branches are stale relative to current main. |
| `codex/w2c-queue-architecture` and phase / confirmation / registrar-batch / wizard families | `PARTIALLY_IN_MAIN` | high | `REIMPLEMENT` | Large stale wave with many runtime assumptions and history-heavy docs. |
| `codex/post-w2c-board-state-*` and `codex/post-w2c-queues-stats-*` clusters | `PARTIALLY_IN_MAIN` | high | `MANUAL_PORT` | Interesting queue ideas remain, but the branches are broad and doc-heavy; port only narrow verified slices. |
| `codex/startup-operator-first-hardening` | `CONFLICTS_WITH_MAIN_DIRECTION` | high | `KEEP_AS_REFERENCE_ONLY` | Huge runtime surface and conflict-prone with current main; use as reference, not as a merge source. |
| `w15 checkpoint branches` | `FULLY_ALREADY_IN_MAIN` | none | `DROP` | Zero-diff checkpoints; they add no recovery value. |
| `codex/emr-v2-deprecation / fix-ci-lab-bootstrap / lab-workflow-release / landing-factory-seed` | `FULLY_ALREADY_IN_MAIN` | none | `DEFER` | These branches are already absorbed or null-diff relative to current main. |
| `123` | `CONFLICTS_WITH_MAIN_DIRECTION` | high | `DROP` | Legacy macOS/admin snapshot plus dotfile / legacy queue file churn. |
| `feat/macos-ui-refactor` | `CONFLICTS_WITH_MAIN_DIRECTION` | high | `DROP` | Binary database snapshot, not a safe code recovery source. |
| `docs/QUEUE_SYSTEM_ARCHITECTURE.md` | `PARTIALLY_IN_MAIN` | medium | `MANUAL_PORT` | Still the active queue SSOT, but needs wording refresh against current main. |
| `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md` and older queue docs | `SUPERSEDED_BY_MAIN` | medium | `ARCHIVE` | Current main has a different notifications architecture and later queue truth. |

## Practical Reading
- `CHERRY_PICK` is reserved only for the small dependency-maintenance refs.
- `MANUAL_PORT` means the idea may survive, but the branch itself is stale or too broad to merge.
- `REIMPLEMENT` means the current main architecture is the right starting point.
- `DROP` means the branch should not be recovered unless a very narrow evidence-backed slice is proven later.
