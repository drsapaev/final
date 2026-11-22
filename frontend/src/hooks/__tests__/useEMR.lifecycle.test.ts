/**
 * Fail-first regression suite: EMR v2 hook write-path identity and conflict
 * discard semantics (audit 3886, round 17).
 *
 * - EMRSIGN-FE-001     — save/sign/amend must serialize the LIVE document
 *   (latest reducer state), not the snapshot captured in the render closure
 *   where the callback was created.
 * - EMRCONFLICT-FE-001 — reloadFromServer() resolves the conflict as an
 *   explicit DISCARD: the freshly loaded server snapshot stays clean and no
 *   follow-up write is scheduled.
 * - EMRCONFLICT-FE-002 — the hook no longer exposes forceOverwrite (the
 *   backend rejects the row_version=0 bypass for genuine conflicts).
 *
 * Red-first: on the pre-fix source, the sign request serializes the stale
 * closure document, reloadFromServer marks the state dirty (autosave
 * immediately re-writes the server content), and forceOverwrite exists.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client', () => ({
    apiClient: {
        get: vi.fn(),
        post: vi.fn(),
    },
    setSessionInvalidationListener: vi.fn(),
}));

import { apiClient } from '../../api/client';
import { useEMR } from '../useEMR';

const apiClientMock = vi.mocked(apiClient);

let visitSeq = 10;

const serverEmr = (overrides: Record<string, unknown> = {}) => ({
    id: 1,
    patient_id: 2,
    visit_id: 10,
    version: 2,
    row_version: 5,
    status: 'in_progress',
    data: { complaints: 'first', specialty: 'therapy' },
    ...overrides,
});

function flush() {
    return new Promise<void>((resolve) => setTimeout(resolve, 0));
}

async function renderLoadedHook(overrides: Record<string, unknown> = {}) {
    // The hook keeps a module-level emrCache keyed by visitId — every test
    // must use a FRESH visitId so a previous test's cache entry can never
    // swallow this test's first GET mock.
    const visitId = visitSeq++;
    apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr({ ...overrides, visit_id: visitId }) });
    const utils = renderHook(() => useEMR(visitId, { specialty: 'therapy' }));
    await waitFor(() => {
        expect(utils.result.current.emr).not.toBeNull();
    });
    return utils;
}

describe('EMRSIGN-FE-001: write paths serialize the live document', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('saveEMR sends the latest document, not the closure snapshot', async () => {
        const utils = await renderLoadedHook();
        apiClientMock.post.mockResolvedValue({ status: 200, data: serverEmr({ row_version: 6 }) });

        // Edit AFTER the hook render — the old implementation serialized the
        // render-time snapshot ('first'), losing 'first plus second'.
        act(() => {
            utils.result.current.setField('complaints', 'first plus second');
        });

        await act(async () => {
            await utils.result.current.saveEMR({ isDraft: true });
        });

        const payload = apiClientMock.post.mock.calls[0][1] as { data: Record<string, unknown>; row_version: number; reason?: string };
        expect(payload.data.complaints).toBe('first plus second');
        expect(payload.row_version).toBe(5);
    });

    it('signEMR sends the latest document with the returned row version', async () => {
        const utils = await renderLoadedHook();
        apiClientMock.post.mockResolvedValue({ status: 200, data: serverEmr({ row_version: 8, status: 'signed' }) });

        act(() => {
            utils.result.current.setField('diagnosis', 'confirmed by echo');
        });

        await act(async () => {
            await utils.result.current.signEMR({ rowVersion: 7 });
        });

        const payload = apiClientMock.post.mock.calls[0][1] as { data: Record<string, unknown>; row_version: number; reason?: string };
        expect(payload.data.diagnosis).toBe('confirmed by echo');
        expect(payload.row_version).toBe(7);
    });

    it('amendEMR sends the latest document', async () => {
        const utils = await renderLoadedHook({ status: 'signed' });
        apiClientMock.post.mockResolvedValue({ status: 200, data: serverEmr({ row_version: 6, status: 'amended' }) });

        act(() => {
            utils.result.current.setField('treatment', 'corrected dosage');
        });

        await act(async () => {
            await utils.result.current.amendEMR('Correction of a clerical error');
        });

        const payload = apiClientMock.post.mock.calls[0][1] as { data: Record<string, unknown>; row_version: number; reason?: string };
        expect(payload.data.treatment).toBe('corrected dosage');
        expect(payload.reason).toBe('Correction of a clerical error');
    });
});

describe('EMRSAVE-FE-001 (hook level): late ACK keeps newer edits dirty', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('a save ACK for the older snapshot keeps the newer text visibly unsaved', async () => {
        const utils = await renderLoadedHook();
        let resolveSave: (v: { status: number; data: unknown }) => void = () => {};
        apiClientMock.post.mockImplementation(
            () => new Promise((resolve) => { resolveSave = resolve; }),
        );

        let savePromise!: Promise<unknown>;
        act(() => {
            utils.result.current.setField('complaints', 'first');
        });
        await act(async () => {
            savePromise = utils.result.current.saveEMR({ isDraft: true });
        });

        // Doctor types B while save(A) is pending
        act(() => {
            utils.result.current.setField('complaints', 'first plus second');
        });

        // ACK for the older snapshot arrives
        await act(async () => {
            resolveSave({ status: 200, data: serverEmr({ row_version: 6 }) });
            await savePromise;
        });

        expect(utils.result.current.isDirty).toBe(true);
        expect(utils.result.current.data.complaints).toBe('first plus second');

        // The next save must include B
        apiClientMock.post.mockClear();
        apiClientMock.post.mockResolvedValue({ status: 200, data: serverEmr({ row_version: 7 }) });
        await act(async () => {
            await utils.result.current.saveEMR({ isDraft: true });
        });
        const payload = apiClientMock.post.mock.calls[0][1] as { data: Record<string, unknown>; row_version: number; reason?: string };
        expect(payload.data.complaints).toBe('first plus second');
        expect(payload.row_version).toBe(6);
    });
});

describe('EMRCONFLICT-FE-001: reloadFromServer resolves as an explicit discard', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('leaves the freshly loaded server snapshot clean (no phantom dirty, no re-write)', async () => {
        const utils = await renderLoadedHook();

        // Force a 409 conflict on save (axios-style rejection)
        apiClientMock.post.mockRejectedValueOnce({
            response: {
                status: 409,
                data: { detail: { current_version: 9, your_version: 5, last_edited_by: 42, last_edited_at: '2026-11-08T00:00:00Z' } },
            },
        });
        act(() => {
            utils.result.current.setField('complaints', 'local edit');
        });
        await act(async () => {
            await utils.result.current.saveEMR({ isDraft: true });
        });
        expect(utils.result.current.hasConflict).toBe(true);
        // The conflict save itself consumed one POST — reset the call log so
        // the final assertion only sees writes scheduled AFTER the discard.
        apiClientMock.post.mockClear();

        // Doctor discards: reload from server (fresh GET with new content)
        apiClientMock.get.mockResolvedValueOnce({
            status: 200,
            data: serverEmr({ row_version: 9, data: { complaints: 'server B', specialty: 'therapy' } }),
        });
        await act(async () => {
            await utils.result.current.reloadFromServer();
        });

        expect(utils.result.current.hasConflict).toBe(false);
        expect(utils.result.current.isDirty).toBe(false);
        expect(utils.result.current.data.complaints).toBe('server B');

        // No write may be scheduled for the discarded state
        await act(async () => { await flush(); });
        expect(apiClientMock.post).not.toHaveBeenCalled();
    });
});

describe('EMRCONFLICT-FE-002: force overwrite is gone', () => {
    it('does not expose forceOverwrite', async () => {
        vi.clearAllMocks();
        const utils = await renderLoadedHook();
        expect((utils.result.current as Record<string, unknown>).forceOverwrite).toBeUndefined();
    });
});
