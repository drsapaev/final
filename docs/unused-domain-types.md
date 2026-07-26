# Unused Domain Types Backlog

**Generated:** 2026-07-24
**Source:** `scripts/domain-metrics.ts` (ZERO USAGE section)
**Total:** 47 of 132 domain interfaces (35.6%) have zero references in the codebase.

## Policy

Each week, for every type in this list, take exactly ONE of two actions:

1. **Adopt** — find a consumer that should use this type, migrate it, verify Coverage metric rises.
2. **Delete** — if no real consumer exists after search, remove the type from `types/domain/*.ts`.

Unused domain types drift out of sync with the backend contract and become toxic.
**Leaving them "for later" is not an option** — they must either prove their value or be removed.

## Backlog (sorted by domain file)

### `types/domain/ai.ts`
- [ ] AIChatRole
- [ ] AIChatMessageType
- [ ] AIImageAnalysisFinding
- [ ] AIImageAnalysisResult

### `types/domain/appData.ts`
- [ ] AppLoadingState
- [ ] AppErrorsState

### `types/domain/auth.ts`
- [ ] UserRole
- [ ] AuthStatus
- [ ] AuthSessionState (reserved for future auth UI refactor — keep until G7+)
- [ ] AuthUser
- [ ] AuthAction
- [ ] LoginCredentials
- [ ] TokenPayload
- [ ] SessionInfo

### `types/domain/billing.ts`
- [ ] PaymentStatus
- [ ] DiscountMode
- [ ] InvoiceItem
- [ ] DiscountApplication
- [ ] BillingSummary
- [ ] RefundStatus
- [ ] PaymentProvider
- [ ] PaymentWebhook
- [ ] CartItemBilling

### `types/domain/chat.ts`
- [ ] ChatMessageType
- [ ] ChatOnlineStatus
- [ ] ChatOnlineStatusMap
- [ ] ChatTypingMap

### `types/domain/clinic.ts`
- [ ] AppointmentStatus
- [ ] AppointmentType
- [ ] QueueNumberInfo
- [ ] DoctorScheduleSlot
- [ ] DoctorAvailability
- [ ] DepartmentStats
- [ ] ServiceCategory

### `types/domain/emr.ts`
- [ ] EMRRecord
- [ ] EMRDiagnosis
- [ ] EMRPrescription
- [ ] EMRLabResult
- [ ] EMRAISuggestion
- [ ] EMRVisitType
- [ ] EMRVisitData
- [ ] EMRConflict
- [ ] EMRSaveResult
- [ ] EMRSectionConfig

### `types/domain/queue.ts`
- [ ] QueueSource
- [ ] QueueAction
- [ ] QueueJoinInfo

## Triage rules

- **`*Status`, `*Type`, `*Mode`** string-literal unions — usually safe to delete if the consuming code uses inline string literals. Adopt only if a switch/case or discriminated union would benefit from the named type.
- **`*Response`, `*Request`** envelopes — likely candidates for adoption in Wave 4 follow-up (move transport types into `api/` and convert via mapper).
- **`*Action`** discriminated unions for reducers — adopt only when the corresponding reducer is migrated to typed actions.
- **`AuthSessionState`** — explicitly reserved for future work (G7+ auth UI refactor). Do not delete without team discussion.

## Review cadence

- **Weekly:** review 5-10 types from this list.
- **Action per type:** either move to "Adopted" (commit migration) or delete (commit removal).
- **Metric:** `Average coverage` and `Total unused` in `scripts/domain-metrics.ts` output should trend DOWN over time as types find consumers or are removed.
