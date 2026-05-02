# PR Review Practice Track

Use this 12-week practice track with `docs/runbooks/PR_REVIEW_QUALITY_GATES.md`.

The quality gates define what every risky PR must prove. This track defines how the team builds that review muscle week by week using real pull requests, small exercises, and repeatable evidence.

## Operating Rhythm

Each two-week sprint should end with one reusable artifact:

- one completed PR gate checklist from a real PR
- one targeted regression or browser smoke proof
- one short note about a repeated failure mode that the next PR should avoid

Keep the cadence small:

- Review no more than one risky PR per week through the full gate.
- Use narrow tests or smoke checks first.
- Treat docs-only and process-only changes as practice for scope discipline.
- Prefer one precise prevention rule over broad cleanup.

## Weeks 1-2: Contract-First API/WS

Goal:
- Make contract impact visible before implementation details dominate the review.

Exercise:
- Pick one PR that changes an endpoint, websocket payload, event name, or frontend API consumer.
- Fill the `Contract Impact` section in the PR template.
- Identify one canonical surface and one compatibility path, even if the compatibility path is `none`.
- Add or point to one targeted proof.

Reviewer checklist:
- Does the PR name the backend surface and frontend consumer?
- Are status codes and expected empty states clear?
- Is every alias marked as legacy, compatibility, or canonical?
- Does the proof exercise the shape that the frontend actually consumes?

Sprint artifact:
- One completed `Contract Impact` block pasted into the PR discussion or PR body.

## Weeks 3-4: RBAC And Role Matrix

Goal:
- Catch permission drift before it appears as random 403/500 behavior in panel smoke.

Exercise:
- Pick one PR that changes endpoint dependencies, route guards, role helpers, or specialist panel routing.
- Fill the `RBAC / Permissions` PR section.
- Prove one allowed role and one denied role.

Reviewer checklist:
- Is role normalization handled in the shared helper instead of endpoint-local special casing?
- Does the changed route have a deny-path proof?
- Do sibling routes accept roles consistently?
- Are legacy list-form role inputs normalized before authorization decisions?

Sprint artifact:
- One small role matrix update or PR comment showing `role -> allowed/denied -> proof`.

## Weeks 5-6: Notification Policy

Goal:
- Move notification behavior from accidental producer behavior to an explicit policy decision.

Exercise:
- Pick one notification producer, inbox path, websocket delivery path, or Telegram-related path.
- Fill the `Notification / Realtime` PR section for event type, severity, recipients, channel, and policy gates.
- Prove one preference or quiet-hours case when the PR touches delivery behavior.

Reviewer checklist:
- Does one server-side policy decision control delivery?
- Are event aliases and deep links canonical?
- Are severity bypasses explicit?
- Are muted channel, quiet hours, or weekend behavior covered when relevant?

Sprint artifact:
- One event catalog row or policy proof comment attached to the PR.

## Weeks 7-8: Realtime Reliability

Goal:
- Make reconnect, read-state, and unread counters converge reliably.

Exercise:
- Pick one chat, notification websocket, read/unread, attachment, or voice flow.
- Run the realtime smoke from `PR_REVIEW_QUALITY_GATES.md`.
- Capture fresh browser context evidence for any failure before classifying it as environment noise.

Reviewer checklist:
- Does reconnect duplicate reliable events?
- Does read state converge from backend state after refresh?
- Are unknown payload fields treated as compatible?
- Is contract-version drift logged without breaking compatible clients?

Sprint artifact:
- One clean-session smoke note with user IDs, route, network log, and result.

## Weeks 9-10: Frontend Resilience And Fallbacks

Goal:
- Ensure panels keep mandatory workflows usable when optional or legacy paths fail.

Exercise:
- Pick one registrar, doctor, specialist, lab, cashier, or admin panel PR.
- Fill the `Frontend Resilience` PR section.
- Prove empty data, partial data, and one expected forbidden secondary path or missing draft state.

Reviewer checklist:
- Does a 403 from a non-required fallback path avoid breaking the mandatory workflow?
- Does an expected 404 bootstrap state render as a draft or empty state?
- Do deep links keep the intended `patientId`, `visitId`, and `tab` context?
- Are request storms prevented through cache, guards, or idempotent loaders?

Sprint artifact:
- One browser smoke proof or issue comment showing resilience behavior.

## Weeks 11-12: Scope And Release Readiness

Goal:
- Prevent contaminated PRs and pre-merge CI/env surprises.

Exercise:
- Pick one risky or surgical PR.
- Fill the `Scope Gate` section before reviewing implementation details.
- Compare the diff against allowed and denied path classes.
- Record migration, docs, tests, rollback note, and validation proof.

Reviewer checklist:
- Are allowed paths named before review?
- Are denied paths named for surgical PRs?
- Are unrelated runtime files treated as contamination until justified?
- Are lockfiles, ports, Postgres-first defaults, CORS, and migration proof addressed when relevant?

Sprint artifact:
- One completed scope gate comment before merge.

## Filled Example: Recovery-Only Surgical PR

Use this as the starter pattern for PRs similar to the PR contamination recovery case.

Contract Impact:
- Canonical surface: docs and workflow/dependency constraints only.
- Request shape: not applicable - no request body or query contract changed.
- Response shape: not applicable - no response payload contract changed.
- Status codes: not applicable - no endpoint status behavior changed.
- Frontend consumer: not applicable - no frontend runtime consumer changed.
- Compatibility path or alias: not applicable - no route, endpoint, or alias changed.
- Contract proof: diff inspection confirms no runtime API/frontend consumer changed.

RBAC / Permissions:
- Roles allowed: not applicable - no route, guard, or permission surface changed.
- Roles denied: not applicable - no route, guard, or permission surface changed.
- Positive auth proof: not applicable - no auth-sensitive behavior changed.
- Negative auth proof: not applicable - no auth-sensitive behavior changed.

Notification / Realtime:
- Event type or websocket channel: not applicable - no event or websocket surface changed.
- Payload version / ack behavior: not applicable - no realtime payload behavior changed.
- Read/unread or delivery semantics: not applicable - no delivery state behavior changed.
- Reconnect/resync proof: not applicable - no reconnect or resync behavior changed.

Frontend Resilience:
- Empty data proof: not applicable - no user-facing data flow changed.
- Partial data proof: not applicable - no user-facing data flow changed.
- Forbidden secondary path behavior: not applicable - no secondary request path changed.
- Missing draft/resource behavior: not applicable - no draft or resource bootstrap path changed.
- Stale route/deep-link behavior: not applicable - no route state behavior changed.

Scope Gate:
- Allowed paths: `docs/recovery/**`, approved recovery packet docs, selected workflow/dependency constraint files.
- Denied paths: broad `frontend/src/**`, broad `backend/app/services/**`, generated output, unrelated runtime UI files.
- Migration/docs/test impact: docs-only recovery packet unless listed workflow/dependency files change.
- Rollback note: revert the surgical docs/workflow branch; no runtime migration rollback expected.

Validation:
- Targeted tests or smoke run: diff inspection against allowed path list.
- Result: no runtime files outside allowed path classes.
- Not checked: runtime browser/API smoke, because the PR intentionally does not change runtime behavior.

## Measurement

Track these small metrics after each sprint:

| Metric | Target by week 12 |
|---|---|
| Contract drift caught during review | Increasing early, then trending down. |
| RBAC issues found after merge | Zero for changed endpoint surfaces. |
| Realtime unread/read drift after reconnect | Zero in smoke for changed realtime flows. |
| PRs with unclear scope | Zero for risky PRs. |
| CI/env failures from lockfile, port, or Postgres/SQLite drift | Zero repeats. |

If a metric repeats twice, add a candidate project rule through the normal rules workflow instead of expanding the checklist indefinitely.
