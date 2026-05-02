# PR Review Quality Gates

Use this runbook for pull requests that touch backend APIs, frontend consumers, RBAC, realtime messaging, notifications, specialist panels, release scripts, or CI.

It turns the 12-week skills plan into reusable review artifacts. The goal is to prevent the repeat issues seen in recent PR and audit work: contract drift, RBAC regressions, unstable websocket/read-state behavior, PR scope contamination, CI/env drift, and weak negative-path proof.

For week-by-week practice, reviewer exercises, and a filled surgical PR example, use `docs/runbooks/PR_REVIEW_PRACTICE_TRACK.md`.

## Two-Week Skill Track

| Weeks | Focus | Required artifact |
|---|---|---|
| 1-2 | Contract-first API/WS | PR includes Contract Impact section and at least one contract proof when behavior changes. |
| 3-4 | RBAC and role matrix | PR includes positive and negative auth proof for changed endpoint surfaces. |
| 5-6 | Notification policy | Notification PRs define event catalog row and policy decision path before delivery code changes. |
| 7-8 | Realtime reliability | WS/chat PRs include reconnect, resync, and unread/read convergence proof. |
| 9-10 | Frontend resilience | Panel PRs include empty, partial, forbidden-secondary-path, and stale-route handling proof. |
| 11-12 | PR scope and release readiness | Risky PRs include allowed paths, denied paths, rollback note, and narrow validation proof. |

## Contract Impact Checklist

Complete this section for every API, websocket, event, or frontend consumer change.

| Field | Required answer |
|---|---|
| Canonical surface | Endpoint, websocket channel, event type, or frontend consumer. |
| Request shape | Required fields, optional fields, validation rules, and defaults. |
| Response shape | Required fields, nullable fields, pagination/envelope, and error envelope. |
| Status codes | Success, validation, auth, conflict, not found, and expected empty-state codes. |
| Frontend consumer | Component, hook, context, or service reading this contract. |
| Compatibility path | Legacy alias, redirect, fallback, or explicit `none`. |
| Contract proof | Test, browser smoke, API smoke, or reason no behavior changed. |

REST contract rule:
- If a backend endpoint changes shape or status behavior, add or update one targeted backend contract regression.
- If a frontend consumer changes shape assumptions, add or update one frontend shape test, smoke, or documented browser proof.

Websocket/event contract rule:
- Every reliable event must define `event_name`, `payload_version`, `required_payload_fields`, `ack/read semantics`, and reconnect/resync behavior.
- Any alias or rename, for example `diagnostics_return` vs `diagnostics_return_needed`, must be marked as a compatibility path with owner and removal condition.

Example backend contract proof:

```python
def test_registrar_services_contract_keeps_laboratory_group(client, admin_token):
    response = client.get(
        "/api/v1/registrar/services",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "laboratory" in payload
    assert all("id" in item and "name" in item for item in payload["laboratory"])
```

Example frontend consumer proof:

```javascript
it("maps registrar service payload without relying on code-prefix fallback", () => {
  const payload = { laboratory: [{ id: 130, name: "QA Lab", queue_tag: "lab" }] };

  expect(mapRegistrarServices(payload).laboratory).toHaveLength(1);
  expect(mapRegistrarServices(payload).procedures).toHaveLength(0);
});
```

## RBAC Review Matrix

Use this matrix when a PR changes routes, endpoint dependencies, role helpers, auth guards, or specialist panels.

| Role | Primary surfaces | Must prove |
|---|---|---|
| `admin` | `/admin/*`, settings, users, security, audit, integrations | Admin-only routes reject non-admin users. |
| `registrar` | `/registrar`, patient/visit intake, queue handoff, service catalog consumers | Registrar can create and update allowed visit/payment handoff flows only. |
| `doctor` | `/doctor`, general doctor queue, visit/EMR actions | Doctor cannot access admin surfaces and uses canonical queue-entry actions. |
| `dentist` | `/doctor/dentistry`, dental APIs, visit protocols | Dentist role is accepted by dental clinician endpoints and rejects unrelated role surfaces. |
| `lab` | `/lab`, lab queue, report instances, templates | Lab can create/update allowed reports and rejects invalid template choices. |
| `cashier` | `/cashier`, payments, receipt/refund flows | Cashier payment actions update downstream status without broader admin access. |
| `patient` | `/patient`, public/patient-owned surfaces | Patient sees only patient-owned data and cannot access operator panels. |

RBAC implementation rule:
- Role normalization lives in the shared auth/RBAC helper, not in endpoint-local one-off checks.
- Legacy role forms, list-form role inputs, and canonical varargs must converge before endpoint authorization decisions.
- A changed endpoint needs at least one positive role proof and one deny-path proof.

Minimum negative proof set for risky PRs:
- `doctor` cannot access `/api/v1/admin/*`.
- `dentist` can access dental endpoints but cannot use unrelated specialist endpoints.
- Legacy list-form role input is normalized once and does not produce sibling-route divergence.

## Notification Policy Checklist

Use this before changing notification producers, inbox delivery, realtime delivery, Telegram wiring, or notification settings.

| Field | Required answer |
|---|---|
| Event type | Canonical name, aliases, and owner. |
| Severity | `info`, `warning`, `critical`, or local enum equivalent. |
| Recipients | Role, user, patient, queue, or department targeting source. |
| Channels | Inbox, websocket, Telegram, SMS/email, or explicit `none`. |
| Deep link | Canonical route and fallback when unavailable. |
| Policy gates | Preferences, quiet hours, weekend rule, severity bypass, throttling/dedupe. |
| Tests | Muted channel, quiet hours, and severity bypass when relevant. |

Policy rule:
- Notification delivery must ask one server-side policy decision before writing deliveries or sending realtime/external messages.
- Producers should not bypass user preferences or quiet-hours behavior.
- Severity exceptions must be explicit and tested.

## Realtime Reliability Smoke

Run this smoke after changes to chat, notification websocket, read-state, reconnect, transport payloads, attachment delivery, or voice delivery.

Required checks:
- Login as two users in a fresh browser context.
- Send a message from User A to User B.
- Confirm User B unread count increments before opening the conversation.
- Open the active conversation and confirm unread/read state clears through backend state, not only local UI state.
- Force reconnect or reload and confirm unread/read state converges.
- Capture current console and network logs for failures.
- Classify environment noise only when a fresh context and current network log prove it is not active logic failure.

Done when:
- Reconnect does not duplicate reliable events.
- Unread counters converge after refresh or reconnect.
- Unknown websocket fields remain backward-compatible.
- Contract-version drift is logged without breaking compatible clients.

## Frontend Resilience Checklist

Use this for registrar, doctor, specialist, lab, cashier, and admin panel changes.

Required checks:
- Empty data: the primary workflow shows a stable empty state.
- Partial data: missing optional fields do not crash table rows, cards, or modals.
- Forbidden secondary path: a 403 from a non-required fallback path does not break the mandatory workflow.
- Missing draft/resource: expected 404 bootstrap states render as empty drafts, not fatal alerts.
- Stale route state: deep links with `patientId`, `visitId`, or `tab` keep the intended tab and context.
- Request noise: repeated loaders are cached, guarded, or idempotent enough to avoid request storms.

Specialist panel rule:
- Prefer queue/appointment-derived patient context first.
- Use direct patient endpoints only when the current role is authorized.
- Do not replace canonical queue-entry IDs with visit or appointment IDs when queue actions require entry IDs.

## PR Scope And Release Readiness

Use this gate for every risky PR and every PR that touches runtime code, CI, migrations, release scripts, or production-sensitive docs.

Scope gate:
- Name allowed paths before review.
- Name denied paths when the PR is meant to be surgical.
- Explain any migration, docs, tests, or runbook impact.
- Treat unrelated runtime files in a docs/recovery PR as contamination until justified.

Release readiness gate:
- Lockfiles are present when dependency install paths changed.
- CI docs and workflows use Postgres-first defaults and backend port `18000`.
- Frontend dev/smoke docs use frontend port `5173` unless a temporary stack is explicitly named.
- CORS/origin differences are documented when browser smoke uses a temporary frontend port.
- Migrations include upgrade path and narrow verification target.
- Risky PRs include rollback note and narrow validation proof.

Clean surgical PR example:
- Allowed paths: `docs/recovery/**`, selected runbooks, selected workflow/dependency constraint files.
- Denied paths: broad `frontend/src/**`, broad `backend/app/services/**`, generated output, unrelated runtime UI files.
- Merge condition: diff contains only allowed path classes and the validation proof matches the stated scope.

## PR Ready Checklist

Before requesting review, the PR author confirms:

- Contract Impact is complete or marked `not applicable` with reason.
- RBAC proof is complete for any endpoint, guard, route, or role change.
- Notification/WS policy proof is complete for event or realtime changes.
- Frontend resilience checks are complete for panel changes.
- Scope gate is complete for risky or surgical PRs.
- Release readiness gate is complete for CI, migration, dependency, or deployment changes.

## Lightweight Enforcement

The repository includes a soft PR-body gate for the template sections in `.github/pull_request_template.md`.

Local check:

```powershell
python scripts/check_pr_review_template.py --body-file path\to\pr-body.md
```

CI check:
- `.github/workflows/pr-review-quality-gate.yml` runs on pull requests into `main`.
- The check fails when required sections are missing or left as empty placeholders.
- `not applicable` is accepted when paired with a short reason, so docs-only and surgical PRs can stay lightweight.
