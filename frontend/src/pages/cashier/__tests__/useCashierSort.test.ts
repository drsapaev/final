/**
 * PR-UI-14-6 unit contract: useCashierSort — the history-table client sort
 * state moved verbatim from CashierPanel (UX Audit #4.2).
 */
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useCashierSort } from '../useCashierSort';

describe('useCashierSort (PR-UI-14-6)', () => {
  it('initial state: date field, desc direction', () => {
    const { result } = renderHook(() => useCashierSort());
    expect(result.current.sortField).toBe('date');
    expect(result.current.sortDir).toBe('desc');
  });

  it('toggling the same field flips the direction', () => {
    const { result } = renderHook(() => useCashierSort());
    act(() => result.current.toggleSort('date'));
    expect(result.current.sortField).toBe('date');
    expect(result.current.sortDir).toBe('asc');
    act(() => result.current.toggleSort('date'));
    expect(result.current.sortDir).toBe('desc');
  });

  it('switching fields resets the direction to asc', () => {
    const { result } = renderHook(() => useCashierSort());
    act(() => result.current.toggleSort('patient'));
    expect(result.current.sortField).toBe('patient');
    expect(result.current.sortDir).toBe('asc');
    act(() => result.current.toggleSort('amount'));
    expect(result.current.sortField).toBe('amount');
    expect(result.current.sortDir).toBe('asc');
  });
});
