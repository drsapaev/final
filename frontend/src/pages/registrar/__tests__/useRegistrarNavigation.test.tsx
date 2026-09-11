/**
 * PR-UI-13-5 unit contract: useRegistrarNavigation — the URL-state and
 * entry-point hook extracted from RegistrarPanel.
 *
 * Pins the verbatim-port behavior:
 * - activeTab derives from ?dept= on mount and writes back with replace
 *   (R-02 shareable links; window.location.search is the write source)
 * - currentView derives from the canonical path, not from ?view= (Phase 3)
 * - legacy ?view=welcome|queue redirects replace-only to /registrar/{view}
 *   preserving the other query params (Phase 2)
 * - patientId deep-link resolves the patient and writes their name into ?q=
 *   (404 swallowed silently)
 * - wizard launch triggers: `openAppointmentWizard` header event (P-008),
 *   ?action=new deep link (cleaned from the URL after firing),
 *   Ctrl+N shortcut (skipped while focus is in input/textarea/select)
 *
 * Test-only follow-up: the hook shipped in #2903 without unit tests; these
 * were ported from the superseded #2904 branch onto the merged hook API and
 * extended with the wizard-launch-trigger coverage the merged hook owns.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, afterEach } from 'vitest';

import { useRegistrarNavigation } from '../useRegistrarNavigation';

const getPatient = vi.fn();
vi.mock('../../../api/patients', () => ({
  getPatient: (...args: unknown[]) => getPatient(...args),
}));

function createWizardSetters() {
  return {
    setShowWizard: vi.fn(),
    setWizardEditMode: vi.fn(),
    setWizardInitialData: vi.fn(),
  };
}

function renderNavigationHook(initialPath: string, showWizard = false) {
  const wizardSetters = createWizardSetters();
  const hook = renderHook(
    () => useRegistrarNavigation({ showWizard, ...wizardSetters }),
    {
      wrapper: ({ children }: { children: React.ReactNode }) => (
        <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
      ),
    },
  ).result;
  return { hook, ...wizardSetters };
}

afterEach(() => {
  getPatient.mockReset();
});

describe('useRegistrarNavigation (PR-UI-13-5)', () => {
  it('derives activeTab from ?dept= on mount', () => {
    const { hook } = renderNavigationHook('/registrar?dept=cardio');
    expect(hook.current.activeTab).toBe('cardio');
  });

  it('defaults activeTab to null without ?dept=', () => {
    const { hook } = renderNavigationHook('/registrar');
    expect(hook.current.activeTab).toBe(null);
  });

  it('derives currentView from the canonical path (Phase 3)', () => {
    expect(renderNavigationHook('/registrar/welcome').hook.current.currentView).toBe('welcome');
    expect(renderNavigationHook('/registrar/queue').hook.current.currentView).toBe('queue');
    expect(renderNavigationHook('/registrar').hook.current.currentView).toBe(null);
  });

  it('exposes searchQuery lowercased and statusFilter from the URL', () => {
    const { hook } = renderNavigationHook('/registrar?q=Ivanov&status=done');
    expect(hook.current.searchQuery).toBe('ivanov');
    expect(hook.current.statusFilter).toBe('done');
  });

  it('exposes patientIdFromUrl parsed as an integer', () => {
    const { hook } = renderNavigationHook('/registrar?patientId=42');
    expect(hook.current.patientIdFromUrl).toBe(42);
  });

  it('redirects legacy ?view=welcome to the canonical path preserving params (Phase 2)', async () => {
    const { hook } = renderNavigationHook('/registrar?view=welcome&q=x');
    // The redirect effect is replace-only; once it lands, currentView is
    // canonical, ?view=/?tab= are gone, and ?q= is preserved.
    await waitFor(() => {
      expect(hook.current.currentView).toBe('welcome');
    });
    expect(hook.current.searchParams.get('view')).toBe(null);
    expect(hook.current.searchParams.get('q')).toBe('x');
  });

  it('redirects legacy ?view=queue to the canonical path (Phase 2)', async () => {
    const { hook } = renderNavigationHook('/registrar?view=queue');
    await waitFor(() => {
      expect(hook.current.currentView).toBe('queue');
    });
    expect(hook.current.searchParams.get('view')).toBe(null);
  });

  it('writes the patient name into ?q= for a patientId deep link', async () => {
    getPatient.mockResolvedValue({ last_name: 'Иванов', first_name: 'Иван' });
    const { hook } = renderNavigationHook('/registrar?patientId=42');
    await waitFor(() => {
      expect(hook.current.searchParams.get('q')).toBe('Иванов Иван');
    });
    expect(getPatient).toHaveBeenCalledWith(42);
  });

  it('does not throw and writes no ?q= on a 404 patient lookup', async () => {
    getPatient.mockRejectedValue({ response: { status: 404 } });
    const { hook } = renderNavigationHook('/registrar?patientId=99');
    await act(async () => { await Promise.resolve(); });
    expect(hook.current.searchParams.get('q')).toBe(null);
  });

  it('setActiveTab writes ?dept= through the URL (R-02)', async () => {
    const { hook } = renderNavigationHook('/registrar');
    await act(async () => { hook.current.setActiveTab('derma'); });
    expect(hook.current.activeTab).toBe('derma');
    await act(async () => { hook.current.setActiveTab(null); });
    expect(hook.current.activeTab).toBe(null);
    expect(hook.current.searchParams.get('dept')).toBe(null);
  });

  // RQ-20 (срез RQ-20.a): setActiveTab must build the next query from the
  // ROUTER searchParams. The previous implementation read
  // window.location.search, which diverges from the router location under
  // MemoryRouter (and any basename deployment) — switching tabs silently
  // wiped ?q=/?status= filters.
  it('keeps ?q=/?status= when switching tabs (RQ-20 param preservation)', async () => {
    const { hook } = renderNavigationHook('/registrar?q=ivanov&status=done');
    await act(async () => { hook.current.setActiveTab('derma'); });
    expect(hook.current.searchParams.get('dept')).toBe('derma');
    expect(hook.current.searchParams.get('q')).toBe('ivanov');
    expect(hook.current.searchParams.get('status')).toBe('done');
  });

  // RQ-20 (срез RQ-20.a): tab changes PUSH a history entry (replace kept the
  // URL correct but made Back exit the page instead of restoring the tab),
  // and the hook syncs activeTab when the URL changes under it (the
  // useState initializer alone only ran on mount, so Back changed ?dept=
  // while the UI kept the newer tab).
  it('restores the previous tab on browser back (RQ-20 push + sync)', async () => {
    const { hook } = renderNavigationHook('/registrar');
    await act(async () => { hook.current.setActiveTab('derma'); });
    expect(hook.current.activeTab).toBe('derma');
    expect(hook.current.searchParams.get('dept')).toBe('derma');
    await act(async () => { hook.current.navigate(-1); });
    expect(hook.current.searchParams.get('dept')).toBe(null);
    expect(hook.current.activeTab).toBe(null);
  });

  it('re-applies the tab on browser forward (RQ-20 push + sync)', async () => {
    const { hook } = renderNavigationHook('/registrar');
    await act(async () => { hook.current.setActiveTab('derma'); });
    await act(async () => { hook.current.navigate(-1); });
    expect(hook.current.activeTab).toBe(null);
    await act(async () => { hook.current.navigate(1); });
    expect(hook.current.searchParams.get('dept')).toBe('derma');
    expect(hook.current.activeTab).toBe('derma');
  });

  it('syncs activeTab when ?dept= changes externally while mounted (RQ-20)', async () => {
    const { hook } = renderNavigationHook('/registrar');
    await act(async () => { hook.current.navigate('/registrar?dept=cardio'); });
    expect(hook.current.activeTab).toBe('cardio');
    await act(async () => { hook.current.navigate('/registrar'); });
    expect(hook.current.activeTab).toBe(null);
  });

  it('opens the wizard on the openAppointmentWizard header event (P-008)', () => {
    const { setShowWizard } = renderNavigationHook('/registrar');
    act(() => {
      window.dispatchEvent(new Event('openAppointmentWizard'));
    });
    expect(setShowWizard).toHaveBeenCalledWith(true);
  });

  it('auto-opens the wizard for ?action=new and cleans the URL', async () => {
    const { hook, setShowWizard } = renderNavigationHook('/registrar?action=new');
    await waitFor(() => {
      expect(setShowWizard).toHaveBeenCalledWith(true);
    });
    // The param is cleaned so a refresh does not re-trigger the wizard.
    await waitFor(() => {
      expect(hook.current.searchParams.get('action')).toBe(null);
    });
  });

  it('does not re-open the wizard when it is already open (?action=new guard)', async () => {
    const { setShowWizard } = renderNavigationHook('/registrar?action=new', true);
    await act(async () => { await Promise.resolve(); });
    expect(setShowWizard).not.toHaveBeenCalled();
  });

  it('Ctrl+N opens the wizard in create mode (UX Audit Registrar #17)', () => {
    const { setShowWizard, setWizardEditMode, setWizardInitialData } = renderNavigationHook('/registrar');
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { ctrlKey: true, key: 'n', bubbles: true }));
    });
    expect(setWizardEditMode).toHaveBeenCalledWith(false);
    expect(setWizardInitialData).toHaveBeenCalledWith(null);
    expect(setShowWizard).toHaveBeenCalledWith(true);
  });

  it('Ctrl+N is ignored while focus is in an input', () => {
    const { setShowWizard } = renderNavigationHook('/registrar');
    const input = document.createElement('input');
    document.body.appendChild(input);
    act(() => {
      input.dispatchEvent(new KeyboardEvent('keydown', { ctrlKey: true, key: 'n', bubbles: true }));
    });
    expect(setShowWizard).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });
});
