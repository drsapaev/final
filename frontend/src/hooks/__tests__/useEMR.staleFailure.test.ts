/**
 * RETRO-3930-01 (consolidated post-merge review of #3930, PR #3944) —
 * fail-first.
 *
 * On the merged round-18 source the loadEMR SUCCESS path checked
 * stillCurrentVisit() before dispatching, but the CATCH path did not: a
 * deferred 403/500 of visit A that rejected after the doctor had already
 * switched to an authorized visit B called handleAccessDenied (or dispatched
 * saveError) unconditionally — B's editor got a spurious write-denial /
 * error state (save button locked) even though visit A was no longer
 * current. The round-18 suite covered late SUCCESSFUL loads only.
 *
 * Contract after the fix: every catch/denial path is guarded by the
 * visit+principal request identity —
 *  - a deferred A-403 after B-200: no accessDenied lock, no error state,
 *    and a subsequent save of B is NOT skipped;
 *  - a deferred A-500 after B-200: no stale error state for B;
 *  - a deferred 403 of an in-flight save of A does not lock B's editor.
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

const flush = () => new Promise<void>((r) => setTimeout(r, 0));

// NOTE: the emrCache is module-global and survives across tests — always
// use fresh visit ids (round-18 gotcha).
describe('RETRO-3930-01: late failures of the previous visit cannot lock or error the current one', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        authState.profile = { id: 1 };
    });

    it('a deferred 403 of visit A does not lock or error visit B (and B still saves)', async () => {
        // Visit A mounts; its GET stays pending.
        const gateA = deferred<{ status: number; data: unknown }>();
        apiClientMock.get.mockImplementationOnce(() => gateA.promise);
        const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
            initialProps: { visitId: 60 },
        });

        // The doctor switches to visit B before A answers; B loads fine.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(61) });
        act(() => {
            utils.rerender({ visitId: 61 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-61 text');
        });

        // A's GET finally rejects with 403 — long after A stopped being
        // the current visit.
        await act(async () => {
            gateA.reject({ response: { status: 403, data: { detail: 'forbidden' } } });
            await flush();
        });

        // B must not inherit A's denial or error.
        expect(utils.result.current.accessDenied).toBe(false);
        expect(utils.result.current.error).toBeFalsy();
        expect(utils.result.current.data.complaints).toBe('visit-61 text');

        // And B's editor still saves: the write path is not skipped by a
        // stale writeAccessDenied flag.
        apiClientMock.post.mockResolvedValueOnce({
            status: 200,
            data: serverEmr(61, { row_version: 6, data: { complaints: 'B saved', specialty: 'therapy' } }),
        });
        await act(async () => {
            await utils.result.current.saveEMR();
        });
        expect(apiClientMock.post).toHaveBeenCalledTimes(1);
        expect(utils.result.current.accessDenied).toBe(false);
    });

    it('a deferred 500 of visit A does not write visit B\'s error state', async () => {
        const gateA = deferred<{ status: number; data: unknown }>();
        apiClientMock.get.mockImplementationOnce(() => gateA.promise);
        const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
            initialProps: { visitId: 70 },
        });

        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(71) });
        act(() => {
            utils.rerender({ visitId: 71 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-71 text');
        });

        await act(async () => {
            gateA.reject({ response: { status: 500, data: { detail: 'boom' } } });
            await flush();
        });

        // Late failure of the previous visit: no stale error for B.
        expect(utils.result.current.error).toBeFalsy();
        expect(utils.result.current.data.complaints).toBe('visit-71 text');
    });

    it('a deferred 403 of an in-flight save of visit A does not lock visit B', async () => {
        // Visit A loads, then a save is started and hangs.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(80) });
        const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
            initialProps: { visitId: 80 },
        });
        await waitFor(() => {
            expect(utils.result.current.emr).not.toBeNull();
        });

        const gateSave = deferred<{ status: number; data: unknown }>();
        apiClientMock.post.mockImplementationOnce(() => gateSave.promise);
        await act(async () => {
            void utils.result.current.saveEMR();
        });

        // The doctor switches to visit B while A's save is in flight.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(81) });
        act(() => {
            utils.rerender({ visitId: 81 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-81 text');
        });

        // A's save rejects with 403 after the switch.
        await act(async () => {
            gateSave.reject({ response: { status: 403, data: { detail: 'forbidden' } } });
            await flush();
        });

        // B's editor is not locked by A's late denial…
        expect(utils.result.current.accessDenied).toBe(false);
        expect(utils.result.current.error).toBeFalsy();

        // …and B's own save still works.
        apiClientMock.post.mockResolvedValueOnce({
            status: 200,
            data: serverEmr(81, { row_version: 6, data: { complaints: 'B saved', specialty: 'therapy' } }),
        });
        await act(async () => {
            await utils.result.current.saveEMR();
        });
        expect(apiClientMock.post).toHaveBeenCalledTimes(2);
        expect(utils.result.current.accessDenied).toBe(false);
    });

    it('a conflict reload dropped by a visit switch does not clear the new visit\'s unsaved edits (Codex follow-up)', async () => {
        // Visit A loads, then a conflict «discard» reload is started and hangs.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(90) });
        const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
            initialProps: { visitId: 90 },
        });
        await waitFor(() => {
            expect(utils.result.current.emr).not.toBeNull();
        });

        const gateReload = deferred<{ status: number; data: unknown }>();
        apiClientMock.get.mockImplementationOnce(() => gateReload.promise);
        await act(async () => {
            void utils.result.current.reloadFromServer();
        });

        // The doctor switches to visit B while the reload is in flight.
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(91) });
        act(() => {
            utils.rerender({ visitId: 91 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-91 text');
        });

        // B gets unsaved edits.
        act(() => {
            utils.result.current.setField('complaints', 'unsaved B edit');
        });
        expect(utils.result.current.isDirty).toBe(true);

        // A's reload GET finally fails — the load is dropped as stale.
        await act(async () => {
            gateReload.reject({ response: { status: 500, data: { detail: 'boom' } } });
            await flush();
        });

        // The dropped reload must NOT resolve the current visit's conflict
        // state: B's dirty flag and edits survive untouched.
        expect(utils.result.current.isDirty).toBe(true);
        expect(utils.result.current.data.complaints).toBe('unsaved B edit');
        expect(utils.result.current.error).toBeFalsy();
    });
});
