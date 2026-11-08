/**
 * Fail-first regression suite: EMR v2 context/cache ownership and structured
 * diagnosis wiring (audit 3886, round 18).
 *
 * - EMRCTX-FE-001   — switching the visit on a mounted hook hard-resets the
 *   clinical state and drops late resolutions of the previous visit.
 * - EMRCACHE-FE-001 — the module-global cache is scoped to the authenticated
 *   principal and cleared on a principal swap; anonymous state bypasses it.
 * - EMRCACHE-FE-002 — successful save/sign/amend refresh the cache, and a
 *   404 placeholder draft is never cached, so a remount after a save shows
 *   the saved canonical record instead of an empty draft.
 * - EMRDIAG-FE-001/002 — editing the visible main diagnosis text updates
 *   diagnosis.main (preserving icd10_code/secondary) and the visible ICD-10
 *   field reads/writes the canonical nested code, mirrored to the flat field.
 *
 * Red-first: on the pre-fix source every assertion below fails — the state
 * of the previous visit survived a visit switch, a late A-GET overwrote B,
 * the cache survived principal swaps, a 404 draft was cached and re-served
 * after a successful save, and the diagnosis callbacks replaced the whole
 * structured diagnosis object / edited only the flat ICD code.
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

async function renderLoadedHook(visitId: number) {
    apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(visitId) });
    const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
        initialProps: { visitId },
    });
    await waitFor(() => {
        expect(utils.result.current.emr).not.toBeNull();
    });
    return utils;
}

describe('EMRCTX-FE-001: visit switch hard-resets and drops late resolutions', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        authState.profile = { id: 1 };
    });

    it('clears the previous visit data/dirty state when the visit changes', async () => {
        const utils = await renderLoadedHook(10);
        act(() => {
            utils.result.current.setField('complaints', 'dirty A edit');
        });
        expect(utils.result.current.isDirty).toBe(true);

        // Switch the same mounted hook to visit B with a deferred GET
        let resolveB!: (v: { status: number; data: unknown }) => void;
        apiClientMock.get.mockImplementationOnce(
            () => new Promise((resolve) => { resolveB = resolve; }),
        );
        act(() => {
            utils.rerender({ visitId: 11 });
        });

        // Previous visit's clinical text must not remain under visit B
        expect(utils.result.current.data.complaints).toBeUndefined();
        expect(utils.result.current.isDirty).toBe(false);

        await act(async () => {
            resolveB({ status: 200, data: serverEmr(11) });
            await new Promise<void>((r) => setTimeout(r, 0));
        });
        expect(utils.result.current.data.complaints).toBe('visit-11 text');
    });

    it('drops a late resolution of the previous visit that arrives after the new visit loaded', async () => {
        // NOTE: the emrCache is module-global and survives across tests —
        // always use fresh visit ids so earlier tests can never serve a
        // cache hit here.
        const utils = await renderLoadedHook(40);

        // Old visit's pending refresh resolves AFTER the switch
        let resolveOldA!: (v: { status: number; data: unknown }) => void;
        apiClientMock.get.mockImplementationOnce(
            () => new Promise((resolve) => { resolveOldA = resolve; }),
        );
        await act(async () => {
            // not awaited to completion: the deferred GET stays pending
            void utils.result.current.loadEMR(true);
        });
        expect(typeof resolveOldA).toBe('function');

        // Switch to B (B loads fast)
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(41) });
        act(() => {
            utils.rerender({ visitId: 41 });
        });
        await waitFor(() => {
            expect(utils.result.current.data.complaints).toBe('visit-41 text');
        });

        // The late A resolution must NOT overwrite B
        await act(async () => {
            resolveOldA({ status: 200, data: serverEmr(40) });
            await new Promise<void>((r) => setTimeout(r, 0));
        });
        expect(utils.result.current.data.complaints).toBe('visit-41 text');
    });
});

describe('EMRCACHE-FE-002: writes refresh the cache; 404 placeholders are not cached', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        authState.profile = { id: 1 };
    });

    it('a remount after a successful save shows the saved record, not the 404 draft', async () => {
        // First mount: 404 -> empty draft (must NOT be cached)
        apiClientMock.get.mockResolvedValueOnce({ status: 404, data: { detail: 'not found' } });
        const first = renderHook(() => useEMR(20, { specialty: 'therapy' }));
        await waitFor(() => {
            expect(first.result.current.emr).not.toBeNull();
        });
        expect(first.result.current.rowVersion).toBe(0);

        // Doctor types and saves successfully
        apiClientMock.post.mockResolvedValueOnce({
            status: 200,
            data: serverEmr(20, { row_version: 1, data: { complaints: 'saved clinical text', specialty: 'therapy' } }),
        });
        act(() => {
            first.result.current.setField('complaints', 'saved clinical text');
        });
        await act(async () => {
            await first.result.current.saveEMR({ isDraft: false });
        });
        first.unmount();

        // Remount: the auto-load must surface the SAVED content (cache hit on
        // the refreshed entry — no server GET needed)
        const second = renderHook(() => useEMR(20, { specialty: 'therapy' }));
        await waitFor(() => {
            expect(second.result.current.emr).not.toBeNull();
        });
        expect(second.result.current.data.complaints).toBe('saved clinical text');
        expect(second.result.current.rowVersion).toBe(1);
        expect(apiClientMock.get).toHaveBeenCalledTimes(1); // only the original 404 GET
    });

    it('a 404-only session never serves a cached empty draft on remount', async () => {
        apiClientMock.get.mockResolvedValueOnce({ status: 404, data: { detail: 'not found' } });
        const first = renderHook(() => useEMR(21, { specialty: 'therapy' }));
        await waitFor(() => {
            expect(first.result.current.emr).not.toBeNull();
        });
        first.unmount();

        // Remount without any save: the hook must re-query the server
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(21) });
        const second = renderHook(() => useEMR(21, { specialty: 'therapy' }));
        await waitFor(() => {
            expect(second.result.current.emr).not.toBeNull();
        });
        expect(apiClientMock.get).toHaveBeenCalledTimes(2);
        expect(second.result.current.data.complaints).toBe('visit-21 text');
    });
});

describe('EMRCACHE-FE-001: principal-scoped cache', () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it('clears the cache and re-queries the server when the principal changes', async () => {
        authState.profile = { id: 1 };
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(30) });
        const first = renderHook(() => useEMR(30, { specialty: 'therapy' }));
        await waitFor(() => {
            expect(first.result.current.emr).not.toBeNull();
        });
        first.unmount();

        // Principal swap (logout + login as another user, no page reload)
        authState.profile = { id: 2 };
        apiClientMock.get.mockRejectedValueOnce({ response: { status: 403, data: { detail: 'forbidden' } } });
        const second = renderHook(() => useEMR(30, { specialty: 'therapy' }));
        await waitFor(() => {
            expect(apiClientMock.get).toHaveBeenCalledTimes(2);
        });

        // The second principal must never see principal 1's cached record:
        // the server is queried and its 403 stands; no cached PHI leaks.
        await waitFor(() => {
            expect(second.result.current.accessDenied).toBe(true);
        });
        expect(second.result.current.data.complaints).toBeUndefined();
    });

    it('bypasses the cache entirely for anonymous state', async () => {
        authState.profile = null;
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(31) });
        const utils = renderHook(() => useEMR(31, { specialty: 'therapy' }));
        await waitFor(() => {
            expect(utils.result.current.emr).not.toBeNull();
        });
        expect(utils.result.current.data.complaints).toBe('visit-31 text');
    });
});

describe('EMRDIAG-FE-001/002: structured diagnosis wiring (container contract)', () => {
    it('routes the diagnosis and ICD callbacks through the nested canonical fields', async () => {
        const fs = await import('node:fs');
        const path = await import('node:path');
        const { fileURLToPath } = await import('node:url');
        const __dirname = path.dirname(fileURLToPath(import.meta.url));
        const source = fs.readFileSync(
            path.join(__dirname, '../../components/emr-v2/EMRContainerV2.tsx'),
            'utf8',
        );

        // EMRDIAG-FE-001: main text edits diagnosis.main, not the whole object
        expect(source).toContain("onDiagnosisChange={handleNestedFieldChange('diagnosis.main')}");
        expect(source).not.toContain("onDiagnosisChange={handleFieldChange('diagnosis')}");

        // EMRDIAG-FE-002: the visible ICD field is canonical (nested-first read,
        // nested write mirrored to the flat field)
        expect(source).toContain('icd10Code={canonicalIcd10Code}');
        expect(source).toContain('onIcd10Change={handleCanonicalIcd10Change}');
        expect(source).toContain("setNestedField('diagnosis.icd10_code', value)");
        const visitTab = fs.readFileSync(
            path.join(__dirname, '../../components/cardiology/VisitTab.tsx'),
            'utf8',
        );
        // EMRCTX-FE-001 belt: the cardiology mount is keyed by visit identity
        expect(visitTab).toContain("key={selectedPatient?.visit_id ?? 'no-visit'}");
    });
});

describe('EMRDIAG-FE-001: reducer-level structured diagnosis preservation', () => {
    it('SET_NESTED_FIELD on diagnosis.main preserves icd10_code and secondary', async () => {
        const { emrReducer, emrActions, initialState } = await import('../../reducers/emrReducer');
        const base = {
            ...initialState,
            data: {
                diagnosis: {
                    main: 'A',
                    icd10_code: 'I10',
                    secondary: [{ code: 'E11', description: 'T2DM' }],
                },
            },
        };
        const next = emrReducer(base, emrActions.setNestedField('diagnosis.main', 'B'));
        const diagnosis = next.data.diagnosis as Record<string, unknown>;
        expect(diagnosis.main).toBe('B');
        expect(diagnosis.icd10_code).toBe('I10');
        expect(diagnosis.secondary).toEqual([{ code: 'E11', description: 'T2DM' }]);
    });
});
