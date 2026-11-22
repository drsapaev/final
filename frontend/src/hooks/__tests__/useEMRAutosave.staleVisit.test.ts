/**
 * RETRO-3971-02 (post-merge review of the 3969–3996 window, group 2
 * archive PR #4000) — fail-first regressions for the stale-visit autosave
 * stamping.
 *
 * `useEMR.saveEMR` resolves `null` when the failure belongs to a PREVIOUS
 * visit (the RETRO-3930-01 stale-visit bail: "no stale error state for the
 * current one"). The autosave honesty guards recognized only
 * `accessDenied` / `conflict` — a `null` resolution fell straight into the
 * success bookkeeping (`lastSaveTimeRef.current = Date.now()`,
 * `errorCountRef.current = 0`, `onAutosaveSuccess`), so a hook instance
 * that survives a visit switch carried the previous visit's failure as the
 * NEW visit's "✓ saved" stamp. Reachable in the dermatology panel, which
 * mounts `<EMRContainerV2>` without a per-visit `key` (the cardiology panel
 * keys it — the repo's established per-visit editor semantics), and the
 * conflict test never mocked a `null` resolution.
 *
 * Contract under test (mirrors EMRAUTOSAVE-FE-001's honesty policy):
 * a save that did not happen must not be stamped as the last successful
 * autosave; the transient-error counter follows the conflict policy (no
 * reset, no increment); the next genuinely successful save alone stamps;
 * and the dermatology container is keyed per visit like the cardiology one.
 */
import { act, renderHook } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { fileURLToPath } from 'node:url';

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
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('RETRO-3971-02: a stale-visit null save is not a successful autosave', () => {
  it('a null saveEMR resolution does not stamp the last-successful timestamp', async () => {
    saveEMR.mockResolvedValueOnce(null);
    const { result, rerender } = renderAutosave();

    expect(result.current.lastAutosave).toBeNull();

    await act(async () => {
      await result.current.forceSave();
    });
    rerender();

    // THE core regression: pre-fix, the null fell into the success
    // bookkeeping and stamped Date.now() for a visit whose save never ran.
    expect(result.current.lastAutosave).toBeNull();
    expect(onAutosaveSuccess).not.toHaveBeenCalled();
    // the drop is reported, not swallowed silently
    expect(onAutosaveError).toHaveBeenCalledTimes(1);
    expect((onAutosaveError.mock.calls[0][0] as { type?: string }).type).toBe('staleVisit');
  });

  it('an undefined resolution is treated the same way', async () => {
    saveEMR.mockResolvedValueOnce(undefined as unknown as Record<string, unknown>);
    const { result, rerender } = renderAutosave();

    await act(async () => {
      await result.current.forceSave();
    });
    rerender();

    expect(result.current.lastAutosave).toBeNull();
    expect(onAutosaveSuccess).not.toHaveBeenCalled();
    expect((onAutosaveError.mock.calls[0][0] as { type?: string }).type).toBe('staleVisit');
  });

  it('keeps the transient-error counter intact across a stale-visit drop', async () => {
    // Timer-driven path: forceSave intentionally resets the counter on
    // manual saves, so the policy check must run through the debounced
    // autosave (same harness as the conflict suite).
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

    // End the dirty session, then start a NEW one — that re-arms the
    // debounce timer (the effect keys on the isDirty transition).
    act(() => { dirty = false; });
    rerender();
    act(() => { dirty = true; });
    rerender();

    // Second autosave resolves null (the save belonged to the previous
    // visit). Policy mirrors EMRAUTOSAVE-FE-001's conflict policy: neither
    // resets nor increments the transient counter (pre-fix: reset to 0).
    saveEMR.mockResolvedValueOnce(null);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    rerender();

    expect(saveEMR).toHaveBeenCalledTimes(2);
    expect((onAutosaveError.mock.calls.at(-1)?.[0] as { type?: string }).type).toBe('staleVisit');
    expect(result.current.errorCount).toBe(1);
  });

  it('a subsequent genuinely successful save alone updates the timestamp', async () => {
    saveEMR.mockResolvedValueOnce(null);
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
    expect(result.current.lastAutosave as number).toBeGreaterThan(0);
  });
});

describe('RETRO-3971-02: the dermatology EMR container is keyed per visit', () => {
  it('DermatologistPanelUnified mounts EMRContainerV2 with a per-visit key (cardio precedent)', () => {
    const here = path.dirname(fileURLToPath(import.meta.url));
    const src = fs.readFileSync(
      path.resolve(here, '../../pages/DermatologistPanelUnified.tsx'),
      'utf8',
    ).replace(/\r\n/g, '\n');

    const mountIdx = src.indexOf('<EMRContainerV2');
    expect(mountIdx).toBeGreaterThan(-1);
    const mount = src.slice(mountIdx, src.indexOf('/>', mountIdx) + 2);
    // the key precedes the visitId prop, mirroring VisitTab.tsx's
    // key={selectedPatient?.visit_id ?? 'no-visit'} contract
    const keyIdx = mount.indexOf('key={');
    const visitIdIdx = mount.indexOf('visitId=');
    expect(keyIdx).toBeGreaterThan(-1);
    expect(visitIdIdx).toBeGreaterThan(keyIdx);
    expect(mount).toContain('visit_id');
    expect(mount).toContain('no-visit');
  });
});
