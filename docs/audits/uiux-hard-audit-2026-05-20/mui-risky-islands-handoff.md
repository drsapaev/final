# PR-MUI-4 Risky MUI Islands Handoff

Date: 2026-05-20

## Scope

This is a gated handoff for the remaining risky MUI runtime islands. It does
not migrate runtime UI.

Fresh inventory:

```powershell
rg -l "@mui|Mui" frontend\src\pages frontend\src\components
```

Current post-continuation result: 2 files.

## Global Rule

Do not migrate more than one risky MUI island in a PR.

Each future migration PR must:

- start from fresh `origin/main`;
- use `clinic-ui-ux-master` before editing;
- use `agent_gate.py` or an equivalent narrow handoff when the slice touches a
  strict-mode domain from `AGENTS.md`;
- name canonical anchors, first-touch files, read-only references, validation
  commands, and stop conditions before editing;
- prove no route, RBAC, backend contract, payment, queue, EMR, lab, Telegram,
  notification, or clinical data semantics changed;
- run browser/auth proof for the affected route when the UI is reachable.

## Payment Handoff

Files:

- none currently matching `@mui|Mui`

Note: `frontend/src/pages/PaymentTest.jsx` was migrated to macOS/native
controls in a gate-limited payment demo slice and no longer appears in the MUI
runtime inventory. Future behavior changes to that page still require payment
gate review.
`frontend/src/components/payment/PaymentWidget.jsx` was migrated to
macOS/native controls in a gate-limited payment widget slice and no longer
appears in the MUI runtime inventory. Future behavior changes to the widget
still require payment gate review.

Mode:

- `gate` or `gate_known_root_cause`

First-touch:

- exactly one payment file.

Read-only references:

- payment route owner and tests;
- payment success/cancel result pages;
- backend payment contract docs or endpoint tests if the UI depends on them.

Stop conditions:

- payment amount, status, provider callback, receipt, retry, or error semantics
  change;
- API request/response shape change;
- auth/RBAC or protected route behavior change;
- browser proof cannot reach the payment surface safely.

Validation:

- frontend lint/build;
- targeted payment UI smoke or Playwright route proof;
- static proof no new MUI imports were added;
- PR body contract proof for payment behavior.

## Queue Handoff

File:

- `frontend/src/components/queue/OnlineQueueManager.jsx`

Mode:

- `gate` or `gate_known_root_cause`

First-touch:

- exactly `OnlineQueueManager.jsx`.

Read-only references:

- queue route owner;
- queue join flow;
- specialist/profile/doctor mapping tests or docs;
- queue fairness and `queue_time` guardrails in `AGENTS.md`.

Stop conditions:

- queue ordering, print/download behavior, status wording, specialist mapping,
  or fairness semantics change;
- queue API request/response shape changes;
- browser/auth proof cannot validate the affected queue surface.

Validation:

- frontend lint/build;
- queue browser smoke for the touched state;
- static proof no queue API call or request payload changed.

## Clinical Heavy Handoff

Files:

- none currently matching `@mui|Mui`

Note: `frontend/src/components/laboratory/LabReportGenerator.jsx` had no
active frontend source importer and was removed as stale code. Active lab
panel/report/export behavior remains outside this handoff and unchanged.
`frontend/src/components/patient/FamilyRelationsCard.jsx` was migrated away
from MUI in a dedicated patient relationship slice; future relationship UI
changes remain clinical-gated because pickup-role visibility and family API
behavior are patient-sensitive.
`frontend/src/components/dental/TreatmentPlanner.jsx` was migrated away from
MUI in a dedicated dental planning slice; future treatment plan changes remain
dental/clinical-gated because stage, cost, duration, priority, print, and save
semantics are clinical-sensitive.
`frontend/src/components/dental/ToothModal.jsx` was migrated away from MUI in a
dedicated dental tooth modal slice; future tooth modal changes remain
dental/clinical-gated because procedure selection, material pricing,
follow-up state, notes, history, total price, and save semantics are
clinical-sensitive.
`frontend/src/components/cardiology/ECGViewer.jsx` was migrated away from MUI
in a dedicated cardiology viewer slice; future ECG viewer changes remain
cardiology/clinical-gated because ECG upload metadata, preview/download/delete
behavior, parsed parameters, and AI interpretation semantics are
clinical-sensitive.

Mode:

- `gate` or `gate_known_root_cause`

First-touch:

- exactly one clinical file and one visible UI state family.

Read-only references:

- route/panel owner for the specialty;
- clinical data model/contract references used by the component;
- existing role-specific browser/auth harness;
- audit docs for role workflow and accessibility issues.

Stop conditions:

- clinical status, diagnosis, ECG interpretation, dental treatment/cost, lab
  report, or patient relationship visibility semantics change;
- data transformation, payload, or save/print/export behavior changes;
- browser proof is blocked and the change affects reachable clinical UI.

Validation:

- frontend lint/build;
- role-authenticated browser proof for the affected route and viewport;
- keyboard/focus proof when actions are touched;
- static proof the change is visual-only.

## Telegram / AI Handoff

Files:

- `frontend/src/components/TelegramManager.jsx`

Note: `frontend/src/components/ai/MCPMonitor.jsx` had no active frontend route
owner/importer and was removed as stale code. MCP API client and active AI
assistant surfaces remain outside this handoff and unchanged.

Mode:

- `gate` or `gate_known_root_cause`

First-touch:

- exactly one integration/diagnostic file.

Read-only references:

- `AGENTS.md` Telegram guardrails;
- Telegram Bot API/UX skill guidance only after DB/storage ownership is ruled
  out;
- backend Telegram endpoint/service contracts when status text or actions are
  involved;
- AI/MCP monitoring docs if the UI explains operational diagnostics.

Stop conditions:

- token/security copy, webhook/polling state, bot activation, staff link token,
  MCP diagnostic, or backend status semantics change;
- task mentions Alembic, SQLAlchemy model, table missing, create table,
  storage migration, Postgres SSOT, or revision; switch to migration mode;
- browser/auth proof is unavailable for a reachable integration surface.

Validation:

- frontend lint/build;
- authenticated browser proof for the affected panel;
- static proof no token/secret handling changed;
- PR body proof that no Telegram or AI backend contract changed.

## Shared/Admin Status

No current shared/admin MUI runtime island remains in the active inventory:

- `frontend/src/components/admin/UserManagement.jsx` was migrated away from MUI
  in a dedicated gated admin slice.
- `frontend/src/components/dashboard/Dashboard.jsx` had no confirmed route
  owner and was removed as stale code.

Future admin UI changes still require admin/RBAC proof when they touch user
lifecycle, destructive actions, or role-sensitive behavior.

## Example-Only References

Files:

- `frontend/src/components/examples/UnifiedButton.tsx`
- `frontend/src/components/examples/UnifiedCard.tsx`

These were governed by `mui-example-only-policy.md` and have since been
converted to macOS/native examples.

Do not include them in risky runtime migration PRs.

## Ready-To-Send Prompt Template

```text
Use clinic-ui-ux-master.

Task:
Migrate exactly one MUI island away from MUI without changing runtime behavior.

Target:
<one file only>

Mode:
<gate or gate_known_root_cause>

Required:
- Read AGENTS.md, frontend/DESIGN_SYSTEM.md, frontend/MUI_RUNTIME_INVENTORY.md.
- Confirm route owner and affected role/workflow.
- Name canonical anchors, first-touch file, read-only references, validation commands, and stop conditions before editing.
- Preserve API calls, payloads, status wording, route/RBAC behavior, payment/queue/clinical/Telegram semantics, and backend contracts.
- Use frontend/src/components/ui/macos first.
- Do not add new MUI imports.
- Run lint/build and affected browser/auth proof.

Stop if:
- the slice needs backend/schema/API/route/RBAC behavior changes;
- browser/auth proof is required but unavailable;
- more than one component family must change;
- the file belongs to payment, queue, clinical, Telegram, or AI semantics and the gate does not approve the first-touch file.
```

## Result

PR-MUI-4 created the guardrails needed before any remaining runtime MUI
migration. The current remaining MUI inventory is 2 files across queue and
Telegram surfaces.

## Next Smallest Step

Finish the third cycle with a summary PR that lists:

- merged PRs;
- current performance baseline;
- current MUI inventory;
- blocked/risky MUI handoffs;
- next backlog.
