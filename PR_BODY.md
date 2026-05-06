## Summary

- Replacement for stale PR #90 after parent #89 was superseded by merged PR #268.
- Moves mounted same-day registrar wizard create-branch materialization behind `QueueDomainService.allocate_ticket(allocation_mode="create_entry")`.
- Adds focused unit proof and W2C docs/status updates for the wizard boundary migration.

## Contract Impact

- Canonical surface: `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)` delegates to `QueueDomainService.allocate_ticket(allocation_mode="create_entry")`.
- Request shape: internal `MorningAssignmentCreateBranchHandoff.create_entry_kwargs` remains unchanged.
- Response shape: wizard queue-number payload remains `{queue_tag, queue_id, number, status}`.
- Status codes: not applicable - no HTTP endpoint/status-code behavior is changed.
- Compatibility path or alias: legacy `create_entry_allocator` injection remains as a test/compatibility seam; production default uses `QueueDomainService`.
- Contract proof: `backend/tests/unit/test_wizard_create_branch_extraction.py` proves the default queue-domain allocation path and preserved payload shape.
- Frontend consumer: not applicable - no frontend route, payload consumer, or UI state changed.

## RBAC / Permissions

- Roles allowed: unchanged; this slice does not alter route authorization or role helpers.
- Roles denied: unchanged; no deny/allow policy is modified.
- Positive auth proof: not applicable because the changed service is below the existing wizard authorization layer.
- Negative auth proof: not applicable because no route permission boundary changes.
- Legacy role normalization: not applicable; no role input parsing or normalization changed.

## Notification / Realtime

- Event type or websocket channel: not applicable - no notification or websocket producer changed.
- Payload version / ack behavior: not applicable - no realtime payload changed.
- Read/unread or delivery semantics: not applicable - no notification/read-state behavior changed.
- Reconnect/resync proof: not applicable - no websocket lifecycle behavior changed.

## Frontend Resilience

- Empty data proof: not applicable - no frontend panel, loader, or empty-state behavior changed.
- Partial data proof: not applicable - no frontend data shape or fallback changed.
- Missing draft/resource behavior: not applicable - no EMR draft/resource path changed.
- Stale route/deep-link behavior: not applicable - no route or deep-link behavior changed.
- Empty-state behavior: not applicable - no frontend panel or route changed.
- Partial-data behavior: not applicable - no frontend data loader changed.
- Forbidden secondary path behavior: not applicable - no browser/API fallback changed.
- Request storm guard: not applicable - no frontend request behavior changed.
- Smoke target: backend unit/contract proof only for the wizard boundary seam.

## Scope Gate

- Allowed paths: `backend/app/services/registrar_wizard_queue_assignment_service.py`, `backend/tests/unit/test_wizard_create_branch_extraction.py`, and W2C wizard boundary docs/status files listed in the PR diff.
- Denied paths: frontend files, migrations, CI/workflows, generated artifacts, unrelated queue allocation implementations.
- Migration/docs/test impact: no migrations; W2C docs/status updated; one focused unit test added for default queue-domain delegation.
- Migration impact: none.
- Docs impact: W2C architecture/status docs updated to describe the migrated mounted same-day wizard boundary and deferred shadow/unmounted review.
- Test impact: one focused unit test added for default queue-domain delegation.
- Rollback note: revert this PR to return default wizard create-branch materialization to the previous direct allocator path while keeping PR #267 handoff extraction intact.

## Validation

- Targeted tests or smoke run: exact staged allowlist check; `git diff --cached --check`; `python -m py_compile backend/app/services/registrar_wizard_queue_assignment_service.py backend/tests/unit/test_wizard_create_branch_extraction.py`; `python C:\final\scripts\run_pr_review_gate_checks.py --body-file PR_BODY.md`.
- Result: local narrow validation passes before opening PR; fresh PR CI must pass before merge decision.
- Not checked: full backend pytest suite and browser smoke are deferred to CI because this slice changes only backend service delegation plus docs.
- Local command: exact staged allowlist check.
- Local command: `git diff --cached --check`.
- Local command: `python -m py_compile backend/app/services/registrar_wizard_queue_assignment_service.py backend/tests/unit/test_wizard_create_branch_extraction.py`.
- Local command: `python C:\final\scripts\run_pr_review_gate_checks.py --body-file PR_BODY.md`.
- CI expectation: fresh PR CI must pass before merge decision.
