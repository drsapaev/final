import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useVisitLifecycle } from '../useVisitLifecycle';
import { cacheService } from '../../core/cache/cacheService';

describe('useVisitLifecycle', () => {
  beforeEach(() => {
    cacheService.clear();
    vi.restoreAllMocks();
  });

  it('invalidates cache on visit change', () => {
    const invalidateVisit = vi.spyOn(cacheService, 'invalidateByVisit');
    const invalidatePatient = vi.spyOn(cacheService, 'invalidateByPatient');
    const onVisitChange = vi.fn();
    const onCleanup = vi.fn();

    const { rerender, unmount } = renderHook(
      ({ visitId, patientId }) =>
        useVisitLifecycle(visitId, patientId, {
          invalidateCacheOnChange: true,
          onVisitChange,
          onCleanup,
        }),
      { initialProps: { visitId: 1, patientId: 10 } }
    );

    act(() => {
      rerender({ visitId: 2, patientId: 10 });
    });

    expect(invalidateVisit).toHaveBeenCalledWith(1);
    expect(invalidatePatient).toHaveBeenCalledWith(10);
    expect(onVisitChange).toHaveBeenCalledTimes(1);
    expect(onCleanup).toHaveBeenCalledTimes(1);

    unmount();
  });

  it('provides abort signals for requests', () => {
    const { result, unmount } = renderHook(() =>
      useVisitLifecycle(1, 10, { invalidateCacheOnChange: false })
    );

    const signal = result.current.getAbortSignal();
    expect(signal).toBeDefined();
    expect(signal.aborted).toBe(false);

    result.current.abortAllRequests();
    expect(signal.aborted).toBe(true);

    unmount();
  });
});
