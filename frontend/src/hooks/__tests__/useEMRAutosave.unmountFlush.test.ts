/**
 * RETRO-3971-04 (post-merge review of the 3969–3996 window, group 2
 * archive PR #4000) — fail-first regressions for the unmount flush.
 *
 * A pending autosave debounce was silently discarded when the editor
 * unmounted (SPA navigation / visit switch): only the browser
 * `beforeunload` was guarded (`useBeforeUnload` in EMRContainerV2), the
 * autosave effect cleanup merely cleared the timers, and no router-level
 * guard exists (the router blocker `useNavigationGuard` has zero
 * non-test consumers). Keystrokes inside the pending debounce window
 * (`DEBOUNCE.autosave = 3000`) never reached the server.
 *
 * Contract under test (the ledger's repair direction): unmounting the
 * editor while a debounce is pending performs a FINAL flush attempt —
 * `doAutosave` invoked once through the latest-ref with the latest
 * `saveEMR` closure; the attempt's own guards (canSave, error-pause)
 * decide whether a POST actually fires; a clean editor saves nothing on
 * unmount.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import { useEMRAutosave } from '../useEMRAutosave';

let saveEMR: Mock<(opts?: Record<string, unknown>) => Promise<unknown>>;
let onAutosaveError: Mock<(error: unknown) => void>;
let onAutosaveSuccess: Mock<(result: unknown) => void>;

function renderAutosave(overrides: Record<string, unknown> = {}) {
  return renderHook((props: { isDirty: boolean }) => useEMRAutosave({
    isDirty: props.isDirty,
    isSaving: false,
    isSigned: false,
    status: 'draft',
    saveEMR,
    debounceMs: 50,
    maxWaitMs: 120_000,
    onAutosaveError,
    onAutosaveSuccess,
    ...overrides,
  }), { initialProps: { isDirty: true } });
}

beforeEach(() => {
  vi.useFakeTimers();
  saveEMR = vi.fn<(opts?: Record<string, unknown>) => Promise<unknown>>();
  saveEMR.mockResolvedValue({ id: 7, data: {}, row_version: 3 });
  onAutosaveError = vi.fn<(error: unknown) => void>();
  onAutosaveSuccess = vi.fn<(result: unknown) => void>();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('RETRO-3971-04: a pending autosave debounce is flushed on unmount', () => {
  it('keystrokes inside the pending window are flushed, not discarded', async () => {
    const { unmount } = renderAutosave();

    // The doctor types and navigates away WITHIN the debounce window —
    // the timer has not fired yet.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20);
    });
    expect(saveEMR).not.toHaveBeenCalled();

    // SPA navigation: the editor unmounts. THE core regression: pre-fix
    // the cleanup merely cleared the timers and the keystrokes were lost.
    unmount();
    expect(saveEMR).toHaveBeenCalledTimes(1);
    expect(saveEMR).toHaveBeenCalledWith({ isDraft: true });
  });

  it('a clean editor saves nothing on unmount (control)', async () => {
    const { unmount } = renderAutosave({ isDirty: false });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20);
    });
    unmount();
    expect(saveEMR).not.toHaveBeenCalled();
  });

  it('the flush attempt respects the error-pause policy (control)', async () => {
    // Three consecutive failures pause autosave; a NEW dirty session would
    // re-arm the debounce, then the editor unmounts — the final attempt is
    // still made through doAutosave, but its own error-pause guard keeps
    // it from hammering the failing server.
    const dirty = true;
    const { result, rerender, unmount } = renderHook((props: { isDirty: boolean }) => useEMRAutosave({
      isDirty: props.isDirty,
      isSaving: false,
      isSigned: false,
      status: 'draft',
      saveEMR,
      debounceMs: 50,
      maxWaitMs: 120_000,
      onAutosaveError,
      onAutosaveSuccess,
    }), { initialProps: { isDirty: dirty } });

    saveEMR.mockRejectedValue(new Error('network down'));
    for (let i = 0; i < 3; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(80);
      });
      // end the dirty session, then start a new one — re-arms the debounce
      act(() => { rerender({ isDirty: false }); });
      act(() => { rerender({ isDirty: true }); });
    }
    expect(result.current.isPausedDueToErrors).toBe(true);
    const callsAfterFailures = saveEMR.mock.calls.length;
    expect(callsAfterFailures).toBeGreaterThanOrEqual(3);

    // unmount while a dirty session exists — the paused policy holds:
    // no additional POST fires on unmount
    unmount();
    expect(saveEMR.mock.calls.length).toBe(callsAfterFailures);
  });
});
