// src/types/features/payment.ts
// Phase 0.5 — Payment domain UI types (placeholder).
// Will be filled in during Phase 5.4 (payment components migration).
//
// SSOT:
//   - frontend/src/components/payment/
//   - backend OpenAPI schemas: PaymentInitRequest, PaymentInitResponse, PayMeConfig, ClickConfig
//
// PayMeConfig and ClickConfig already re-exported from '@/types/api' —
// this file will hold UI-only payment state (PaymentFlowState, form values).

// TODO Phase 5.4: PaymentFlowState, PaymentFormValues
export type PaymentFlowState = Record<string, unknown>;
