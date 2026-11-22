/**
 * EMRAUTOSAVE-FE-001 (audit 3886, round 29) — fail-first regressions for
 * the autosave conflict bookkeeping.
 *
 * Pre-fix source: doAutosave stamped `lastSaveTimeRef.current = Date.now()`
 * and reset `errorCountRef.current = 0` BEFORE testing `result.conflict` —
 * a 409 conflict was recorded as the "last successful autosave" (the
 * timestamp the clinical status display reads) and wiped the transient-
 * error accounting, while the doctor was actually looking at a Conflict
 * state that a successful save never resolved.
 *
 * Contract under test (the finding's repair direction): conflict handling
 * precedes any success bookkeeping; a genuine success alone updates the
 * last-successful timestamp; the error counter follows the documented
 * conflict policy (no reset, no increment).
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { useEMRAutosave } from '../useEMRAutosave';

let saveEMR: Mock<(opts?: Record<string, unknown>) => Promise<unknown>>;
let onAutosaveError: Mock<(error: unknown) => void>;
let onAutosaveSuccess: Mock<(result: unknown) => void>;

function renderAutosave(overrides: Record<string, unknown> = {}) {
  return renderHook(() => useEMRAutosave({
    isDirty: true,
    isSaving: false,
    isSigned: false,
    status: 'draft',
    saveEMR,
    debounceMs: 60_000,
    maxWaitMs: 120_000,
    onAutosaveError,
    onAutosaveSuccess,
    ...overrides,
  }));
}

beforeEach(() => {
  vi.useRealTimers();
  saveEMR = vi.fn<(opts?: Record<string, unknown>) => Promise<unknown>>();
  onAutosaveError = vi.fn<(error: unknown) => void>();
  onAutosaveSuccess = vi.fn<(result: unknown) => void>();
});

afterEach(() => {
  // custom/no-fake-timers-without-cleanup: never leak fake timers.
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('EMRAUTOSAVE-FE-001: a 409 conflict is not a successful autosave', () => {
  it('does not stamp the last-successful timestamp and reports exactly one conflict', async () => {
    saveEMR.mockResolvedValueOnce({ conflict: true, current_version: 7, server_version: 8 });
    const { result, rerender } = renderAutosave();

    expect(result.current.lastAutosave).toBeNull();

    await act(async () => {
      await result.current.forceSave();
    });
    rerender();

    expect(onAutosaveError).toHaveBeenCalledTimes(1);
    expect((onAutosaveError.mock.calls[0][0] as { type?: string }).type).toBe('conflict');
    expect(onAutosaveSuccess).not.toHaveBeenCalled();
    // THE core regression: the conflict must not be stamped as the last
    // successful save (pre-fix: Date.now()).
    expect(result.current.lastAutosave).toBeNull();
  });

  it('a subsequent genuinely successful save alone updates the timestamp', async () => {
    saveEMR.mockResolvedValueOnce({ conflict: true, current_version: 7 });
    const { result, rerender } = renderAutosave();

    await act(async () => {
      await result.current.forceSave();
    });
    rerender();
    expect(result.current.lastAutosave).toBeNull();

    saveEMR.mockResolvedValueOnce({ id: 11, data: {}, row_version: 9 });
    await act(async () => {
      await result.current.forceSave();
    });
    rerender();

    expect(onAutosaveSuccess).toHaveBeenCalledTimes(1);
    expect(result.current.lastAutosave).not.toBeNull();
    expect(result.current.lastAutosave).toBeGreaterThan(0);
  });

  it('keeps the transient-error counter intact across a conflict (timer-driven autosaves)', async () => {
    vi.useFakeTimers();
    let dirty = true;
    const { result, rerender } = renderHook(() => useEMRAutosave({
      isDirty: dirty,
      isSaving: false,
      isSigned: false,
      status: 'draft',
      saveEMR,
      debounceMs: 50,
      maxWaitMs: 120_000,
      onAutosaveError,
      onAutosaveSuccess,
    }));

    // First autosave: transient network error -> errorCount becomes 1.
    saveEMR.mockRejectedValueOnce(new Error('network down'));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(80);
    });
    rerender();
    expect(result.current.errorCount).toBe(1);
    expect((onAutosaveError.mock.calls.at(-1)?.[0] as { type?: string }).type).toBe('error');

    // End the dirty session, then start a NEW one — that is what re-arms
    // the debounce timer (the effect keys on the isDirty transition).
    act(() => { dirty = false; });
    rerender();
    act(() => { dirty = true; });
    rerender();

    // Second autosave: 409 conflict. Policy: neither resets nor increments
    // the transient-error counter (pre-fix: reset to 0).
    saveEMR.mockResolvedValueOnce({ conflict: true, current_version: 3 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    rerender();

    expect(saveEMR).toHaveBeenCalledTimes(2);
    expect((onAutosaveError.mock.calls.at(-1)?.[0] as { type?: string }).type).toBe('conflict');
    expect(result.current.errorCount).toBe(1);
  });
});
