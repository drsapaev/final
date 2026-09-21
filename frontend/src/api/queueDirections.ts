/**
 * RQ-18 — permanent direction address (frontend service module).
 *
 * Backend surface (RQ-16.d, merged #3316 — consumed AS-IS, no second
 * backend implementation):
 *   POST /queue/admin/directions/{profile_key}/public-address/provision
 *     Admin-only, IDEMPOTENT: the first call generates the opaque public
 *     code ONCE; a re-provision returns the SAME address (created=false).
 *     The admin UI recovers the public_code after reload through this
 *     idempotent contract — no GET-public-code endpoint is added.
 *   POST /queue/public/{public_code}/start-session
 *     ONE canonical anonymous resolve/start operation (E-055 §9): it
 *     ALREADY creates the QueueJoin session (session_token + queue_info)
 *     — the permanent /q/:publicCode route must call it exactly once per
 *     mount and feed the response into the existing QueueJoin flow.
 *
 * Types come from the generated contract (openapi.json is authoritative;
 * RQ-16.d shapes already exist there — no regeneration in RQ-18).
 */

import { api } from './client';
import type {
    PublicAddressProvisionResponseDto,
    PublicDirectionStartResponseDto,
} from '../types/api';

export type PublicAddressProvisionResponse = PublicAddressProvisionResponseDto;
export type PublicDirectionStartResponse = PublicDirectionStartResponseDto;

/** Admin-only, idempotent provision of the permanent /q/<public_code>. */
export async function provisionPublicAddress(
    profileKey: string,
): Promise<PublicAddressProvisionResponse> {
    const res = await api.post(
        `/queue/admin/directions/${encodeURIComponent(profileKey)}/public-address/provision`,
    );
    return (res as { data: PublicAddressProvisionResponse }).data;
}

/**
 * Anonymous start of the short-lived session through the permanent
 * address. Creates a NEW session per call — safe to retry as a
 * session-start (no business action), never confused with the complete
 * registration retry honesty (RQ-10).
 */
export async function startPublicDirectionSession(
    publicCode: string,
): Promise<PublicDirectionStartResponse> {
    const res = await api.post(
        `/queue/public/${encodeURIComponent(publicCode)}/start-session`,
    );
    return (res as { data: PublicDirectionStartResponse }).data;
}
