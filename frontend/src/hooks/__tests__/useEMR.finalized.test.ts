/**
 * RETRO-3971-03 (post-merge review of the 3969–3996 window, group 2
 * archive PR #4000) — fail-first regressions for the FINALIZED_STATE 409
 * routing.
 *
 * The backend deliberately returns a structured 409
 * `{"error":"FINALIZED_STATE","message":…}` when the EMR was already
 * signed/amended on the server — amendment routing, not a version
 * conflict. The client's 409 branches (save and sign) read only the
 * `current_version`/`your_version`/`last_edited_by`/`last_edited_at`
 * shape, so a FINALIZED_STATE rejection dispatched `conflictDetected`
 * with undefined versions — the doctor saw the FALSE
 * "Документ был изменён другим пользователем" cause with literal
 * `vundefined/vundefined` (EMRConflictDialog), and the amendment
 * affordance stayed gated behind the LOCAL isSigned flag (false in this
 * scenario), so the designed routing never appeared.
 *
 * Contract after the fix: a FINALIZED_STATE 409 is never classified as a
 * conflict (no conflict state, no dialog), surfaces the honest
 * "already signed — use the amendment flow" error the 400-branch already
 * uses, and resolves with a `{ finalized: true }` marker the autosave
 * hook treats as deterministic (never stamped as a successful save).
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import { useEMRAutosave } from '../useEMRAutosave';
import { useEMR } from '../useEMR';

const authState = vi.hoisted(() => ({ profile: { id: 1 } as { id: number } | null }));

vi.mock('../../api/client', () => ({
    apiClient: { get: vi.fn(), post: vi.fn() },
    setSessionInvalidationListener: vi.fn(),
}));

vi.mock('../../stores/auth', () => ({
    getState: () => ({ profile: authState.profile }),
}));

import { apiClient } from '../../api/client';

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

const finalizedRejection = () => ({
    response: {
        status: 409,
        data: {
            detail: {
                error: 'FINALIZED_STATE',
                message: 'Cannot edit signed or amended EMR. Use amend endpoint instead.',
            },
        },
    },
});

let visitSeq = 900;
async function renderLoadedHook() {
    const visitId = ++visitSeq;
    apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(visitId) });
    const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
        initialProps: { visitId },
    });
    await act(async () => {
        await vi.waitFor(() => {
            expect(utils.result.current.isLoading).toBe(false);
        });
    });
    return utils;
}

beforeEach(() => {
    vi.resetAllMocks();
    authState.profile = { id: 1 };
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe('RETRO-3971-03: a FINALIZED_STATE 409 is amendment routing, not a version conflict', () => {
  it('a FINALIZED_STATE save rejection never sets the conflict state', async () => {
    const utils = await renderLoadedHook();

    apiClientMock.post.mockRejectedValueOnce(finalizedRejection());
    act(() => {
      utils.result.current.setField('complaints', 'late edit over a server-signed EMR');
    });
    let outcome: Record<string, unknown> | undefined;
    await act(async () => {
      outcome = await utils.result.current.saveEMR({ isDraft: true }) as Record<string, unknown>;
    });

    // THE core regression: pre-fix this dispatched conflictDetected and the
    // status became 'conflict' (the false "another user changed" dialog).
    expect(utils.result.current.hasConflict).toBe(false);
    expect(utils.result.current.conflict).toBeNull();
    // the honest surfacing: the same error family the 400-branch uses
    expect(utils.result.current.error).toContain('подписана');
    // the marker the autosave hook classifies as deterministic
    expect(outcome?.finalized).toBe(true);
  });

  it('a FINALIZED_STATE rejection on the sign path surfaces the same honest routing', async () => {
    const utils = await renderLoadedHook();

    apiClientMock.post.mockRejectedValueOnce(finalizedRejection());
    let outcome: Record<string, unknown> | undefined;
    await act(async () => {
      outcome = await utils.result.current.signEMR() as Record<string, unknown>;
    });

    expect(utils.result.current.hasConflict).toBe(false);
    expect(utils.result.current.conflict).toBeNull();
    expect(utils.result.current.error).toContain('подписана');
    expect(outcome?.finalized).toBe(true);
  });

  it('a genuine version-conflict 409 still routes to the conflict dialog (control)', async () => {
    const utils = await renderLoadedHook();

    apiClientMock.post.mockRejectedValueOnce({
      response: {
        status: 409,
        data: { detail: { current_version: 9, your_version: 5, last_edited_by: 42, last_edited_at: '2026-11-08T00:00:00Z' } },
      },
    });
    act(() => {
      utils.result.current.setField('complaints', 'concurrent edit');
    });
    let outcome: Record<string, unknown> | undefined;
    await act(async () => {
      outcome = await utils.result.current.saveEMR({ isDraft: true }) as Record<string, unknown>;
    });

    // unchanged: the true conflict path keeps its versions and dialog
    expect(utils.result.current.hasConflict).toBe(true);
    expect(utils.result.current.conflict?.serverVersion).toBe(9);
    expect(utils.result.current.conflict?.yourVersion).toBe(5);
    expect(outcome?.conflict).toBe(true);
  });
});

describe('RETRO-3971-03: the autosave hook treats a finalized outcome as deterministic', () => {
  let saveEMR: Mock<(opts?: Record<string, unknown>) => Promise<unknown>>;
  let onAutosaveError: Mock<(error: unknown) => void>;
  let onAutosaveSuccess: Mock<(result: unknown) => void>;

  beforeEach(() => {
    vi.useRealTimers();
    saveEMR = vi.fn<(opts?: Record<string, unknown>) => Promise<unknown>>();
    onAutosaveError = vi.fn<(error: unknown) => void>();
    onAutosaveSuccess = vi.fn<(result: unknown) => void>();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('a { finalized: true } save result is never stamped as a successful autosave', async () => {
    saveEMR.mockResolvedValueOnce({ finalized: true, error: 'FINALIZED_STATE' });
    const { result, rerender } = renderHook(() => useEMRAutosave({
      isDirty: true,
      isSaving: false,
      isSigned: false,
      status: 'draft',
      saveEMR,
      debounceMs: 60_000,
      maxWaitMs: 120_000,
      onAutosaveError,
      onAutosaveSuccess,
    }));

    await act(async () => {
      await result.current.forceSave();
    });
    rerender();

    expect(result.current.lastAutosave).toBeNull();
    expect(onAutosaveSuccess).not.toHaveBeenCalled();
    expect(onAutosaveError).toHaveBeenCalledTimes(1);
    expect((onAutosaveError.mock.calls[0][0] as { type?: string }).type).toBe('finalized');
  });
});
