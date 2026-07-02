[<- Previous Page](SECURITY_CHECKLIST.md) | [Back to README](../README.md) | [Next Page ->](TESTING.md)

# AI Module

## Safety Position

AI must help only with drafts, suggestions, explanations, and internal knowledge lookup. Final medical decisions require doctor or admin approval.

## Verified Current Work

- Legacy `/api/v1/ai/*` now has a coarse router-level AI RBAC dependency.
- `/api/v1/emr/ai/*` now requires AI permissions instead of generic auth.
- `/api/v1/emr/ai/suggestions/health` is no longer public.
- EMR AI responses now include draft-only metadata such as `decision_boundary: "suggestion_only"` and `requires_doctor_confirmation: true`.
- `AIAssistant.jsx` now displays a visible human-confirmation warning and handles provider-unavailable responses as errors.

## Preferred Architecture

1. Read-only context gathering.
2. RAG against clinic-approved protocols/templates.
3. Draft generation.
4. Doctor/admin approval.
5. Audit trail for prompt version, input class, output, actor, and approval.
6. Feedback capture and evaluation dataset.
7. Provider configuration and fallback policy.

## Residual Risks

- `AIManager` still initializes a mock provider by default.
- Legacy `/api/v1/ai/*` endpoints are not yet migrated to the safer `/api/v1/ai/v2` gateway response contract.
- Other visible AI surfaces still need the same visible safety/fallback audit.
- External-provider sensitive-data handling still needs end-to-end verification.

## See Also

- [Security Checklist](SECURITY_CHECKLIST.md)
- [API](API.md)
- [Testing](TESTING.md)
