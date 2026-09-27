/**
 * Public visit-confirmation service (PWA/SMS invitation deep link).
 *
 * Backend surface:
 *   POST /visits/info {token}
 *     Public visit card for the invitation link (no confirmation side
 *     effects). The legacy GET /visits/info/{token} remains for older
 *     clients and returns the same patient-safe card (no internal
 *     Visit.notes on either route — PR 3407 delta review P2); this
 *     page keeps the bearer token out of request URLs.
 *     404 = token unknown, 400 = already processed / expired.
 *   POST /patient/visits/confirm
 *     Confirms the pending visit for the token. Same-day confirmations
 *     also issue queue numbers. 404 = unknown/already confirmed, 400 =
 *     wrong channel/expired, 429 = rate limited (retry later).
 *
 * The invitation SMS is built in backend
 * app/services/notifications_pkg/_formatting.py as
 * <FRONTEND_URL>/confirm-visit?token=… — this module feeds the public
 * /confirm-visit screen that consumes the endpoints above.
 */

import { api } from './client';
import type { VisitConfirmationResponseDto } from '../types/api';

export type VisitConfirmationResponse = VisitConfirmationResponseDto;

/** Queue ticket issued when a same-day visit is confirmed (queue_numbers entry). */
export interface VisitQueueNumberDto {
    queue_tag: string;
    number: number;
    queue_id: number;
}

/** POST /visits/info response; mirrors the published VisitInfoResponse
 * schema (patient-safe: no internal Visit.notes on any token-addressed
 * route — PR 3390 review P2 + PR 3407 delta review P2). */
export interface VisitInfoByTokenDto {
    success: boolean;
    visit_id: number;
    status: string;
    patient_name: string;
    doctor_name: string;
    visit_date: string;
    visit_time: string | null;
    department: string | null;
    discount_mode: string | null;
    services: Array<{
        name: string;
        code: string | null;
        quantity: number;
        price: number;
        total: number;
    }>;
    total_amount: number;
    currency: string;
    confirmation_expires_at: string | null;
}

/**
 * Split-origin CSRF contract (PR 3390 review P1): the documented
 * VITE_API_BASE_URL deployment (frontend origin ≠ API origin) still runs
 * the backend CSRFMiddleware, which validates the double-submit pair
 * (csrf_token cookie + X-CSRF-Token header). The CSRF bootstrap GET already
 * uses withCredentials; without it on these POSTs the browser would omit the
 * cookie on the cross-origin request and the backend would answer
 * 403 missing_cookie. Same-origin deployments are unaffected (cookies are
 * always sent there).
 */
const WITH_CREDENTIALS = { withCredentials: true } as const;

/** Public visit card for the invitation token — no confirmation side effects. */
export async function getVisitInfoByToken(
    token: string,
): Promise<VisitInfoByTokenDto> {
    const res = await api.post('/visits/info', { token }, WITH_CREDENTIALS);
    return (res as { data: VisitInfoByTokenDto }).data;
}

/**
 * Confirm the pending visit from the PWA screen. Retrying a FAILED call
 * is safe: the backend claims the visit atomically and rejects tokens
 * that already moved on (404 “already confirmed”).
 */
export async function confirmVisitByPwa(
    token: string,
): Promise<VisitConfirmationResponse> {
    const res = await api.post(
        '/patient/visits/confirm',
        { token },
        WITH_CREDENTIALS,
    );
    return (res as { data: VisitConfirmationResponse }).data;
}
