/**
 * RETRO-3930-01 (post-merge review #3944) — stale cross-visit denials and
 * errors in useEMR.
 *
 * Red-first: on pre-fix source the loadEMR catch path called
 * handleAccessDenied('loadEMR', …) WITHOUT the visit-epoch check, and the
 * save/sign/amend catches had the same hole. A late 401/403 (or any late
 * failure) of visit A that resolved AFTER the hook switched to an
 * authorized visit B unconditionally set writeAccessDeniedRef=true,
 * writeAccessDenied=true and dispatched A's error into B's editor — locking
 * B's saves behind a denial that belonged to a visit nobody was looking at.
 *
 * Contract:
 *  - a late A-403 after B-200 leaves B unlocked (accessDenied=false), with
 *    no stale error state and B's data intact, and B's saveEMR still POSTs;
 *  - a late A-500 after B-200 writes no error state into B;
 *  - a stale A-save 403 resolving after the switch to B does not lock B's
 *    writer — B's subsequent save POSTs and succeeds;
 *  - a stale sign-conflict (409) of A does not open the conflict UI on B.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authState = vi.hoisted(() => ({ profile: { id: 1 } as { id: number } | null }));

vi.mock('../../api/client', () => ({
    apiClient: { get: vi.fn(), post: vi.fn() },
    setSessionInvalidationListener: vi.fn(),
}));

vi.mock('../../stores/auth', () => ({
    getState: () => ({ profile: authState.profile }),
}));

import { apiClient } from '../../api/client';
import { useEMR } from '../useEMR';

const apiClientMock = vi.mocked(apiClient);

const serverEmr = (visitId: number, overrides: Record<string, unknown> = {}) => ({
    id: 1,
    patient_id: 2,
    visit_id: visitId,
    version: 2,
    row_version: 5,
    status: 'in_progress',
    data: { complaints: `visit-${visitId} text`, specialty: 'therapy' },
    ...overrides,
});

function deferred<T>() {
    let resolve!: (v: T) => void;
    let reject!: (e: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

beforeEach(() => {
    vi.resetAllMocks();
    authState.profile = { id: 1 };
});

describe('RETRO-3930-01: a late denial/failure of visit A cannot lock visit B', () => {
    it('late A-load 403 after B-200: B stays unlocked, no stale error, B saves successfully', async () => {
        // NOTE: emrCache is module-global — fresh visit ids per test.
        // A's GET hangs.
        const gateA = deferred<{ status: number; data: unknown }>();
        apiClientMock.get.mockImplementationOnce(() => gateA.promise);

        const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
            initialProps: { visitId: 50 },
        });

        // Switch to authorized visit B before A resolves; B loads fast.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(51) });
        act(() => {
            utils.rerender({ visitId: 51 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-51 text');
        });

        // A's GET rejects with 403 AFTER B is already displayed.
        await act(async () => {
            gateA.reject({ response: { status: 403, data: { detail: 'forbidden A' } } });
            await new Promise<void>((r) => setTimeout(r, 0));
        });

        // B must not inherit A's lock…
        expect(utils.result.current.accessDenied).toBe(false);
        // …nor A's error message (no stale toast/error state).
        expect(utils.result.current.error).toBeNull();
        // …and B's canonical data stays.
        expect(utils.result.current.data.complaints).toBe('visit-51 text');

        // B's save is NOT short-circuited by the stale denial: it POSTs.
        apiClientMock.post.mockResolvedValueOnce({
            status: 200,
            data: serverEmr(51, { row_version: 6, data: { complaints: 'saved by B', specialty: 'therapy' } }),
        });
        await act(async () => {
            await utils.result.current.saveEMR();
        });
        expect(apiClientMock.post).toHaveBeenCalledTimes(1);
        expect(apiClientMock.post.mock.calls[0][0]).toBe('/v2/emr/51');
    });

    it('late A-load 500 after B-200 writes no error state into B', async () => {
        // A's forced refresh hangs (promise caught so the rejection belongs
        // to A's own caller, mirroring a fire-and-forget refresh).
        const gateA = deferred<{ status: number; data: unknown }>();
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(60) });
        const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
            initialProps: { visitId: 60 },
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-60 text');
        });

        apiClientMock.get.mockImplementationOnce(() => gateA.promise);
        const refreshA = utils.result.current.loadEMR(true).catch(() => 'failed-A');

        // Switch to B (loads fast) while A's refresh is pending.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(61) });
        act(() => {
            utils.rerender({ visitId: 61 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-61 text');
        });

        await act(async () => {
            gateA.reject({ response: { status: 500, data: { detail: 'server exploded for A' } } });
            await refreshA;
        });

        // A's late failure must not surface as B's error state.
        expect(utils.result.current.error).toBeNull();
        expect(utils.result.current.accessDenied).toBe(false);
        expect(utils.result.current.data.complaints).toBe('visit-61 text');
    });

    it('stale A-save 403 resolving after the switch to B does not lock B\u2019s writer', async () => {
        // A loads normally.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(70) });
        const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
            initialProps: { visitId: 70 },
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-70 text');
        });

        // A's save hangs on the POST.
        const postGate = deferred<{ status: number; data: unknown }>();
        apiClientMock.post.mockImplementationOnce(() => postGate.promise);
        const saveA = utils.result.current.saveEMR().catch(() => 'failed-save-A');

        // Switch to B before A's POST settles; B loads fast.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(71) });
        act(() => {
            utils.rerender({ visitId: 71 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-71 text');
        });

        // A's save is denied with 403 — AFTER the switch.
        await act(async () => {
            postGate.reject({ response: { status: 403, data: { detail: 'forbidden save A' } } });
            await saveA;
        });

        // B's writer is not locked by A's stale denial…
        expect(utils.result.current.accessDenied).toBe(false);
        expect(utils.result.current.error).toBeNull();

        // …and B's own save POSTs and succeeds.
        apiClientMock.post.mockResolvedValueOnce({
            status: 200,
            data: serverEmr(71, { row_version: 6, data: { complaints: 'saved by B', specialty: 'therapy' } }),
        });
        await act(async () => {
            await utils.result.current.saveEMR();
        });
        expect(apiClientMock.post).toHaveBeenCalledTimes(2);
        expect(apiClientMock.post.mock.calls[1][0]).toBe('/v2/emr/71');
    });

    it('stale A-sign 409 resolving while B is saving does not open B\u2019s conflict UI', async () => {
        // A loads normally.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(80) });
        const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
            initialProps: { visitId: 80 },
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-80 text');
        });

        // A's sign hangs on the POST.
        const signGate = deferred<{ status: number; data: unknown }>();
        apiClientMock.post.mockImplementationOnce(() => signGate.promise);
        const signA = utils.result.current.signEMR().catch(() => 'failed-sign-A');

        // Switch to B; B loads fast.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(81) });
        act(() => {
            utils.rerender({ visitId: 81 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-81 text');
        });

        // B starts its own save (status → 'saving', its POST gated).
        const postGateB = deferred<{ status: number; data: unknown }>();
        apiClientMock.post.mockImplementationOnce(() => postGateB.promise);
        const saveB = utils.result.current.saveEMR();
        await waitFor(() => {
            expect(utils.result.current.isSaving).toBe(true);
        });

        // A's sign returns a conflict WHILE B's save is in flight. From the
        // 'saving' status the conflict transition is legal — only the
        // visit-epoch guard can keep A's conflict out of B's editor.
        await act(async () => {
            signGate.reject({
                response: {
                    status: 409,
                    data: { detail: { current_version: 9, your_version: 5, last_edited_by: 'x', last_edited_at: 'y' } },
                },
            });
            await signA;
        });

        // B stays in its own save flow — no conflict UI, no error.
        expect(utils.result.current.hasConflict).toBe(false);
        expect(utils.result.current.conflict).toBeNull();
        expect(utils.result.current.error).toBeNull();

        // B's save completes normally.
        await act(async () => {
            postGateB.resolve({
                status: 200,
                data: serverEmr(81, { row_version: 6, data: { complaints: 'saved by B', specialty: 'therapy' } }),
            });
            await saveB;
        });
        expect(utils.result.current.hasConflict).toBe(false);
        expect(utils.result.current.error).toBeNull();
    });
});
