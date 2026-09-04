/**
 * PR-UI-14-6: refund-request contracts & pure helpers (verbatim move from
 * RefundRequestsTable.tsx — behavior-preserving decomposition).
 *
 * Fail-closed backend action guards (mirrors cashierPaymentContracts):
 * availability comes ONLY from available_actions / can_* flags — never
 * from status-string inference (contract-pinned).
 */

// Minimal translation fn signature accepted by the helpers below. Mirrors the
// `useTranslation` adapter shape without coupling this file to its concrete type.
export type RefundTranslationFn = (key: string, options?: Record<string, unknown>) => string;

// Shape of a refund request row surfaced by `/force-majeure/refund-requests`.
// All fields are optional because the backend may omit context fields depending
// on the request status and the caller's permissions.
export interface RefundRequest {
  id?: string | number;
  patient_id?: string | number;
  patient_name?: string;
  amount?: number | string;
  refund_type?: string;
  reason?: string;
  status?: string;
  created_at?: string;
  available_actions?: unknown[];
  can_approve?: boolean;
  can_reject?: boolean;
  can_complete?: boolean;
  [key: string]: unknown;
}

export interface RefundRequestsTableProps {
  onRefresh?: () => void;
}

export const REFUND_ACTION_CAN_FIELD = {
  approve: 'can_approve',
  reject: 'can_reject',
  complete: 'can_complete'
};

export const hasBackendRefundAction = (request: RefundRequest | null | undefined, action: string): boolean => {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }

  if (Array.isArray(request?.available_actions)) {
    return request.available_actions.some(
      (availableAction: unknown) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const canField = REFUND_ACTION_CAN_FIELD[normalizedAction as keyof typeof REFUND_ACTION_CAN_FIELD];
  if (canField && request && Object.prototype.hasOwnProperty.call(request, canField)) {
    return Boolean(request[canField]);
  }

  return false;
};

export const getRefundFilterOptions = (t: RefundTranslationFn) => [
  { value: 'all', label: t('misc.rrt_filter_all') },
  { value: 'pending', label: t('misc.rrt_filter_pending') },
  { value: 'approved', label: t('misc.rrt_filter_approved') },
  { value: 'completed', label: t('misc.rrt_filter_completed') },
  { value: 'rejected', label: t('misc.rrt_filter_rejected') },
];
