# 2026-11-17 — Medical AI response safety metadata gap

- **Severity:** P0 under the repository's medical AI safety rule in `AGENTS.md`.
- **Status:** Open for source remediation and operator verification. Production
  configuration, affected deployments, actual patient exposure and clinical
  impact have not been verified. This record does not establish an active
  production incident or patient harm.
- **Evidence:** [PR #4105, group 110 review](https://github.com/drsapaev/final/pull/4105#issuecomment-6914553347)
  and source inspection at `c254bc110e097afeac6bba0b25f430ca4734c718`.

## Observed contract gap

`AGENTS.md` requires every medical AI response to include
`ai_safety_meta.requires_doctor_confirmation: true`. At the inspected base,
`backend/app/services/ai/ai_interfaces.py` defined gateway responses with a
root-level `requires_doctor_confirmation` field but no required nested object;
`backend/app/api/v1/endpoints/emr_ai.py` similarly emitted root safety fields.
At that same base, `backend/app/api/v1/endpoints/ai.py` returned a bare
list from `/ai/icd-suggest`, and `backend/app/api/v1/endpoints/mcp.py`
returned a bare list from `/mcp/batch`; neither response could carry the
required root metadata, including for an empty list. Other legacy, integration
and MCP paths also require verification at their HTTP boundaries. A root
field alone does not satisfy the nested contract.
Some existing EMR AI paths fail before producing a response; source inspection
or synthetic mocks do not prove live generation or production exposure.

Client code must verify the exact nested boolean before displaying, caching or
applying medical suggestions. A marker states the need for clinician review;
it is not evidence that a suggestion is correct. Previously cached responses
without verifiable metadata must not be silently treated as confirmed-safe.
Manual clinical workflows must remain available if AI fails closed.

## Containment and operational status

No production access, flag change, deployment, restart or live-data action was
performed during this investigation. No universal kill switch has been proven
for all affected families: `backend/app/api/v1/api.py` mounts AI and MCP
routers separately, `backend/app/services/ai_feature_gating.py` applies
per-feature flags, and MCP has its own configuration and fallback paths.
A missing feature-flag record can be treated as enabled; therefore do not infer
containment from an absent flag or from disabling only one AI route. Determine
and verify the actual routing, flags and fallback behavior in the affected
installation before treating any mitigation as effective.

At the inspected base, a gateway cache hit could return before
`_audit_request` in `backend/app/services/ai/ai_gateway.py`; existing usage logs
therefore cannot be assumed to trace every affected response. No live incident
scope or audit completeness conclusion has been made.

## Remediation and follow-up

- Restore and test server-owned nested metadata at each medical response
  boundary, including gateway, legacy/integration, EMR and MCP routes, and
  validate it before the client consumes or caches a response.
- Coordinate clients for the object envelopes replacing the formerly bare
  lists from `POST /api/v1/ai/icd-suggest` and `POST /api/v1/mcp/batch`;
  these are contract changes and old external clients must migrate.
- An authorized operator should assess the deployed versions, enabled paths,
  feature flags, fallback paths and available audit evidence, select and verify
  an effective containment appropriate to that installation, and track live
  impact separately. Do not assume any containment has already occurred.
- Keep this record open until the fix and the deployed behavior have been
  independently verified. Source tests and CI alone are not production proof.
