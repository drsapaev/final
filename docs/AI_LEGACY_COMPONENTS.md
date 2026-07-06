# Archived AI Components

> **Date**: July 2026
> **Branch**: `archive/ai-legacy-components`
> **Reason**: Written for old EMR architecture; not compatible with current AIGateway (`/ai/v2/*`) pipeline. Would need PII anonymization, rate limiting, and audit logging integration before revival.

## Deleted from main

| Component | LOC | Clinical Value | Revival Effort | Priority | Notes |
|---|---|---|---|---|---|
| DrugInteractionChecker | 1487 | HIGH — patient safety, drug-drug interaction warnings | 3 days (update API + data model + PII + AIGateway routing) | P1 | Unique feature, no duplicate. Worth reviving through `/ai/v2/analyze-drug-interactions`. |
| RiskAssessment | 1653 | HIGH — clinical risk scoring for treatment decisions | 3 days | P1 | Unique feature. Worth reviving through `/ai/v2/assess-risk`. |
| SmartScheduling | 1530 | MEDIUM — appointment slot optimization | 2 days | P2 | Unique. Admin efficiency feature. |
| QualityControl | 1311 | MEDIUM — clinical quality metrics dashboard | 2 days | P2 | Unique. Admin reporting. |
| VoiceToText | 1298 | LOW — voice transcription (exists in useAI.jsx hook) | 1 day | P3 | Partial duplicate of `useAI.jsx` line 141 (speech recognition). Component had richer UI. |
| AnalyticsInsights | 1376 | LOW — AI usage analytics (exists in ai_cost_analytics) | 1 day | P3 | Partial duplicate of `/ai/analytics/*` endpoints. |
| MedicalImageAnalyzer | 815 | LOW — image upload + analysis (exists in AIAssistant.jsx) | 1 day | P3 | Duplicate of `AIAssistant.jsx` image analysis path. |
| AIChatWindow | 271 | NONE — broken (calls nonexistent `/ai/doctor-chat`) | N/A | DELETE | Broken endpoint, duplicate of `AIChatWidget.jsx`. |
| AILoader | 107 | NONE — simple spinner component | N/A | DELETE | Trivial, can recreate in 10 lines if needed. |

## Also deleted

- `components/emr-v2/ai/useEMRAI.js` (194 LOC) — duplicate of `hooks/useEMRAI.js`, never imported by any component.

## Revival guide

To revive any component:

1. Checkout the archive branch: `git checkout archive/ai-legacy-components`
2. Copy the component file to `frontend/src/components/ai/`
3. Update API calls from `/ai/*` (legacy) to `/ai/v2/*` (AIGateway)
4. Add `detectPromptInjection()` check before sending user input
5. Use `useAI.jsx` hook pattern (already has injection detection + validation)
6. Add loading/error states following `AIChatWidget.jsx` pattern
7. Add `notify.error()` for user-facing errors (react-toastify)
8. Test with PII anonymization enabled (AIGateway handles this automatically)

## Total impact

- **Deleted**: 10 files, ~10,042 LOC
- **Archive branch**: `archive/ai-legacy-components` (preserves all files for future revival)
- **Active AI frontend**: 6,553 LOC (7 components + 4 hooks + validator + constants + MCP client)
