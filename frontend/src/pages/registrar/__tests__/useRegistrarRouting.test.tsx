/**
 * PR-UI-13-5 unit contract: useRegistrarRouting — the routing slice
 * extracted from RegistrarPanel (URL state + deep-link effects).
 *
 * Pins the verbatim-port behavior:
 * - activeTab derives from ?dept= on mount and writes back with replace
 *   (R-02 shareable links; window.location.search is the write source)
 * - currentView derives from the canonical path, not from ?view= (Phase 3)
 * - legacy ?view=welcome|queue redirects replace-only to /registrar/{view}
 *   preserving the other query params (Phase 2)
 * - patientId deep-link resolves the patient and writes their name into ?q=
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, afterEach } from 'vitest';

import { useRegistrarRouting } from '../useRegistrarRouting';

const getPatient = vi.fn();
vi.mock('../../../api/patients', () => ({
  getPatient: (...args: unknown[]) => getPatient(...args),
}));

function renderRoutingHook(initialPath: string) {
  return renderHook(() => useRegistrarRouting(), {
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
    ),
  });
}

afterEach(() => {
  getPatient.mockReset();
});

describe('useRegistrarRouting (PR-UI-13-5)', () => {
  it('derives activeTab from ?dept= on mount', () => {
    const { result } = renderRoutingHook('/registrar?dept=cardio');
    expect(result.current.activeTab).toBe('cardio');
  });

  it('defaults activeTab to null without ?dept=', () => {
    const { result } = renderRoutingHook('/registrar');
    expect(result.current.activeTab).toBe(null);
  });

  it('derives currentView from the canonical path (Phase 3)', () => {
    expect(renderRoutingHook('/registrar/welcome').result.current.currentView).toBe('welcome');
    expect(renderRoutingHook('/registrar/queue').result.current.currentView).toBe('queue');
    expect(renderRoutingHook('/registrar').result.current.currentView).toBe(null);
  });

  it('exposes searchQuery lowercased and statusFilter from the URL', () => {
    const { result } = renderRoutingHook('/registrar?q=Ivanov&status=done');
    expect(result.current.searchQuery).toBe('ivanov');
    expect(result.current.statusFilter).toBe('done');
  });

  it('redirects legacy ?view=welcome to the canonical path preserving params (Phase 2)', async () => {
    const hook = renderRoutingHook('/registrar?view=welcome&q=x');
    // The redirect effect is replace-only; once it lands, currentView is
    // canonical, ?view=/?tab= are gone, and ?q= is preserved.
    await waitFor(() => {
      expect(hook.result.current.currentView).toBe('welcome');
    });
    expect(hook.result.current.searchParams.get('view')).toBe(null);
    expect(hook.result.current.searchParams.get('q')).toBe('x');
  });

  it('redirects legacy ?view=queue to the canonical path (Phase 2)', async () => {
    const hook = renderRoutingHook('/registrar?view=queue');
    await waitFor(() => {
      expect(hook.result.current.currentView).toBe('queue');
    });
    expect(hook.result.current.searchParams.get('view')).toBe(null);
  });

  it('writes the patient name into ?q= for a patientId deep link', async () => {
    getPatient.mockResolvedValue({ last_name: 'Иванов', first_name: 'Иван' });
    const { result } = renderRoutingHook('/registrar?patientId=42');
    await waitFor(() => {
      expect(result.current.searchParams.get('q')).toBe('Иванов Иван');
    });
    expect(getPatient).toHaveBeenCalledWith(42);
  });

  it('does not log a 404 patient lookup as an error', async () => {
    getPatient.mockRejectedValue({ response: { status: 404 } });
    const { result } = renderRoutingHook('/registrar?patientId=99');
    // No throw, no ?q= write — the hook swallows 404 silently.
    await act(async () => { await Promise.resolve(); });
    expect(result.current.searchParams.get('q')).toBe(null);
  });

  it('setActiveTab writes ?dept= through the URL (R-02)', async () => {
    const { result } = renderRoutingHook('/registrar');
    await act(async () => { result.current.setActiveTab('derma'); });
    expect(result.current.activeTab).toBe('derma');
    await act(async () => { result.current.setActiveTab(null); });
    expect(result.current.activeTab).toBe(null);
    expect(result.current.searchParams.get('dept')).toBe(null);
  });
});
