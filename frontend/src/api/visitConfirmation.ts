/**
 * Public visit-confirmation service (PWA/SMS invitation deep link).
 *
 * Backend surface:
 *   POST /visits/info {token}
 *     Public visit card for the invitation link (no confirmation side
 *     effects). The legacy GET /visits/info/{token} remains for older
 *     clients; this page keeps the bearer token out of request URLs.
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

/** POST /visits/info response; mirrors the published VisitInfoResponse schema. */
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
    notes: string | null;
}

/** Public visit card for the invitation token — no confirmation side effects. */
export async function getVisitInfoByToken(
    token: string,
): Promise<VisitInfoByTokenDto> {
    const res = await api.post('/visits/info', { token });
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
    const res = await api.post('/patient/visits/confirm', { token });
    return (res as { data: VisitConfirmationResponse }).data;
}
