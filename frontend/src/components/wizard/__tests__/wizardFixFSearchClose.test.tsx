/**
 * Fix F — patient search staleness protection & safe wizard close.
 *
 * Audit finding (isolated check #6 + static): search had no stale-response
 * guard, debounce timers survived wizard close, suggestions survived
 * selection/reopen, no error state, and the X button / panel Escape
 * destroyed typed input without confirmation.
 *
 * These tests render the real AppointmentWizardV2 with the API layer mocked
 * and use controllable promise resolvers. Debounce waits use real timers
 * (300ms search, 500ms phone check) via waitFor — fake timers conflict with
 * the provider/dialog initialization path.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen, render, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../../test/renderWithProviders';

// ---- Mock the API layer before importing the wizard ----
vi.mock('../../../api/client', () => {
  const apiMock = {
    get: vi.fn().mockResolvedValue({ data: { services: [], doctors: [], queue_profiles: [] } }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  };
  return {
    api: apiMock,
    buildApiUrl: (path: string) => `http://test${path}`,
    buildWsUrl: (path: string) => `ws://test${path}`,
    default: apiMock,
  };
});

type Pending = { query: string; resolve: (v: unknown) => void; reject: (e: unknown) => void };
const pendingSearches: Pending[] = [];
const pendingPhoneChecks: Pending[] = [];

vi.mock('../../../api/patients', () => ({
  getPatient: vi.fn(),
  createPatient: vi.fn(),
  updatePatient: vi.fn(),
  searchPatientsByPhone: vi.fn((phone: string) =>
    new Promise((resolve, reject) => { pendingPhoneChecks.push({ query: phone, resolve, reject }); })),
  searchPatients: vi.fn((query: string) =>
    new Promise((resolve, reject) => { pendingSearches.push({ query, resolve, reject }); })),
  checkAuthProbe: vi.fn().mockResolvedValue(true),
  createRegistrarCart: vi.fn().mockResolvedValue({ success: true }),
  findPatientByPhoneVariants: vi.fn().mockResolvedValue(null),
}));

vi.mock('../../../utils/tokenManager', () => ({
  default: {
    getAccessToken: vi.fn().mockReturnValue('test-token'),
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
  },
}));

import AppointmentWizardV2 from '../AppointmentWizardV2';
import { useRegistrarHotkeys } from '../../../pages/registrar/useRegistrarHotkeys';

const noop = () => {};
const patientA = { id: 'a-1', fio: 'Ахмедов Ахмед Ахмедович', phone: '+998901111111', birth_date: '1980-01-01' };
const patientB = { id: 'b-2', fio: 'Бекмтов Бек Бекович', phone: '+998902222222', birth_date: '1990-02-02' };

// Plain real-timer sleep (no act wrapper — async act deadlocks with the
// provider/dialog init in this environment).
const waitMs = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// The wizard checks registrar access via useRoleAccess(), which reads the
// auth profile from sessionStorage. Seed a synthetic Registrar profile.
const seedRegistrarProfile = () => {
  window.sessionStorage.setItem(
    'auth_profile',
    JSON.stringify({ id: 1, username: 'test-registrar', role: 'Registrar' })
  );
};

const renderWizard = (props: Record<string, unknown> = {}) => {
  seedRegistrarProfile();
  return renderWithProviders(
    <AppointmentWizardV2 isOpen onClose={noop} onComplete={noop} {...props} />
  );
};

// Query via placeholder — stable on origin/main (label htmlFor/id wiring is Fix E).
const getFio = () => screen.getByPlaceholderText('Введите ФИО для поиска или создания') as HTMLInputElement;
const getPhone = () => screen.getByPlaceholderText('+998 XX XXX XX XX') as HTMLInputElement;

// Wait until the debounced call has been issued (real 300/500ms debounce),
// polling inside act so timer-driven state updates are captured.
const waitForPending = async (arr: Pending[], count: number) => {
  for (let i = 0; i < 40; i++) {
    if (arr.length >= count) return;
    await waitMs(100);
  }
  expect(arr.length).toBe(count);
};

beforeEach(() => {
  vi.clearAllMocks();
  pendingSearches.length = 0;
  pendingPhoneChecks.length = 0;
});

afterEach(() => {
  // (body cleanup left to RTL cleanup in setup.ts)
});

describe('Fix F: search responds only to the latest request', () => {
  it('ignores an older response that resolves after a newer request', async () => {
    renderWizard();

    // Query 1 fires after debounce.
    fireEvent.change(getFio(), { target: { value: 'Ахмедов' } });
    await waitForPending(pendingSearches, 1);
    // Query 2 fires (replaces query 1).
    fireEvent.change(getFio(), { target: { value: 'Бекм' } });
    await waitForPending(pendingSearches, 2);

    // Newer request resolves first with patient B.
    pendingSearches[1].resolve([patientB]);
    await waitFor(() => { expect(screen.getAllByText(/Бекмтов/).length).toBeGreaterThan(0); }, { timeout: 2000 });

    // The OLD request now resolves late with patient A — must be ignored.
    pendingSearches[0].resolve([patientA]);
    await waitMs(80);

    expect(screen.queryByText(/Ахмедов Ахмед/)).toBeNull();
    expect(screen.getAllByText(/Бекмтов/).length).toBeGreaterThan(0);
  });

  it('shows no suggestions when the field is cleared while a request is in flight', async () => {
    renderWizard();

    fireEvent.change(getFio(), { target: { value: 'Ахмедов' } });
    await waitForPending(pendingSearches, 1);

    // User clears the field → new search call with empty query invalidates req #1.
    fireEvent.change(getFio(), { target: { value: '' } });
    await waitMs(400);

    // Late response of the stale request must not repopulate suggestions.
    pendingSearches[0].resolve([patientA]);
    await waitMs(80);

    expect(screen.queryByRole('button', { name: /Ахмедов Ахмед Ахмедович/ })).toBeNull();
  });

  it('keeps the selected card when an older search resolves after selection', async () => {
    renderWizard();

    fireEvent.change(getFio(), { target: { value: 'Ахм' } });
    await waitForPending(pendingSearches, 1);
    fireEvent.change(getFio(), { target: { value: 'Бекм' } });
    await waitForPending(pendingSearches, 2);

    // Request 2 completes; user picks patient B.
    pendingSearches[1].resolve([patientB]);
    await waitFor(() => { expect(screen.getAllByText(/Бекмтов/).length).toBeGreaterThan(0); }, { timeout: 2000 });
    fireEvent.click(screen.getByRole('button', { name: /Бекмтов Бек Бекович/ }));
    await waitMs(30);

    // Stale request 1 resolves late — selection must stay intact, no dropdown.
    pendingSearches[0].resolve([patientA]);
    await waitMs(80);

    expect((getFio() as HTMLInputElement).value).toBe('Бекмтов Бек Бекович');
    expect(screen.queryByRole('button', { name: /Ахмедов Ахмед Ахмедович/ })).toBeNull();
  });
});

describe('Fix F: search error state and retry', () => {
  it('shows a distinct error state with retry, without claiming a new patient will be created', async () => {
    renderWizard();

    fireEvent.change(getFio(), { target: { value: 'Ахмедов' } });
    await waitForPending(pendingSearches, 1);

    pendingSearches[0].reject(new Error('network down'));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Не удалось выполнить поиск');
    expect(alert.textContent).not.toContain('Будет создан новый пациент');

    // Retry issues a fresh request with the current query.
    fireEvent.click(screen.getByRole('button', { name: /Повторить поиск/ }));
    await waitForPending(pendingSearches, 2);
    const retryRequest = pendingSearches[pendingSearches.length - 1];
    expect(retryRequest.query).toBe('Ахмедов');
    retryRequest.resolve([patientA]);
    await waitFor(() => { expect(screen.getAllByText(/Ахмедов Ахмед Ахмедович/).length).toBeGreaterThan(0); }, { timeout: 2000 });
    expect(screen.queryByRole('alert')).toBeNull();
  });
});

describe('Fix F: closing the wizard cleans up async search state', () => {
  it('does not carry suggestions into the next open; debounce timers are cleared', async () => {
    const wizard = renderWizard();

    fireEvent.change(getFio(), { target: { value: 'Ахмедов' } });
    await waitForPending(pendingSearches, 1);
    pendingSearches[0].resolve([patientA]);
    await waitFor(() => { expect(screen.getAllByText(/Ахмедов Ахмед Ахмедович/).length).toBeGreaterThan(0); }, { timeout: 2000 });

    // Close and reopen.
    wizard.rerender(
      <AppointmentWizardV2 isOpen={false} onClose={noop} onComplete={noop} />
    );
    await waitMs(30);
    wizard.rerender(
      <AppointmentWizardV2 isOpen onClose={noop} onComplete={noop} />
    );

    // No suggestions or typed value from the previous session.
    expect(screen.queryByRole('button', { name: /Ахмедов Ахмед Ахмедович/ })).toBeNull();
    expect((getFio() as HTMLInputElement).value).toBe('');
    // No stale request was issued after reopen (pending debounce was cleared on close).
    await waitMs(450);
    expect(pendingSearches.length).toBe(1);
  });
});

describe('Fix F: phone check staleness', () => {
  it('does not show a phone error from an outdated check after the phone changed', async () => {
    renderWizard();

    fireEvent.change(getPhone(), { target: { value: '+998 90 111 11 11' } });
    await waitForPending(pendingPhoneChecks, 1);

    // User edits the phone before the first check resolves.
    fireEvent.change(getPhone(), { target: { value: '+998 90 111 11 12' } });
    await waitForPending(pendingPhoneChecks, 2);

    // Old check (phone ...111) resolves claiming the phone is taken — ignored.
    pendingPhoneChecks[0].resolve([patientA]);
    await waitMs(80);
    expect(screen.queryByText('Пациент с таким номером уже существует')).toBeNull();

    // New check (phone ...112) resolves clean — still no error.
    pendingPhoneChecks[1].resolve([]);
    await waitMs(80);
    expect(screen.queryByText('Пациент с таким номером уже существует')).toBeNull();
  });
});


// The wizard X button lives in the custom header (aria-label = t('misc.aw_close')).
const clickCloseButton = () => {
  const btn = document.querySelector('button[aria-label="Закрыть"]') as HTMLButtonElement | null;
  expect(btn).toBeTruthy();
  fireEvent.click(btn as HTMLButtonElement);
};

describe('Fix F: safe close of the wizard', () => {  it('asks for confirmation before destroying typed input (X button)', async () => {
    let closed = 0;
    renderWizard({ onClose: () => { closed += 1; } });

    fireEvent.change(getFio(), { target: { value: 'Ахмедов Ахмед' } });
    await waitMs(20);

    clickCloseButton();
    const confirmButton = await screen.findByRole('button', { name: 'Закрыть без сохранения' }, { timeout: 2000 });

    // Confirm dialog open, wizard not closed yet.
    expect(closed).toBe(0);
    fireEvent.click(confirmButton);
    await waitFor(() => { expect(closed).toBe(1); }, { timeout: 2000 });
  });

  it('closes immediately when the form is empty (X button)', () => {
    let closed = 0;
    renderWizard({ onClose: () => { closed += 1; } });

    clickCloseButton();

    // Clean form: synchronous close, no confirmation dialog.
    expect(closed).toBe(1);
    expect(screen.queryByRole('button', { name: 'Закрыть без сохранения' })).toBeNull();
  });

  it('Escape goes through the same dirty-aware confirmation', async () => {
    let closed = 0;
    renderWizard({ onClose: () => { closed += 1; } });

    fireEvent.change(getFio(), { target: { value: 'Ахмедов Ахмед' } });
    await waitMs(20);
    fireEvent.keyDown(document, { key: 'Escape' });
    const confirmButton = await screen.findByRole('button', { name: 'Закрыть без сохранения' }, { timeout: 2000 });

    expect(closed).toBe(0);
    fireEvent.click(confirmButton);
    await waitFor(() => { expect(closed).toBe(1); }, { timeout: 2000 });
  });

  it('blocks close while a save is in progress (no false cancellation)', async () => {
    let closed = 0;
    renderWizard({ onClose: () => { closed += 1; }, isProcessing: true });

    fireEvent.change(getFio(), { target: { value: 'Ахмедов Ахмед' } });
    await waitMs(20);
    clickCloseButton();
    await waitMs(80);

    expect(closed).toBe(0);
    expect(screen.queryByRole('button', { name: 'Закрыть без сохранения' })).toBeNull();
  });
});

describe('Fix F: panel Escape no longer bypasses the wizard guard', () => {
  it('useRegistrarHotkeys does not close the wizard on Escape', () => {
    const setShowWizard = vi.fn();
    const setShowSlotsModal = vi.fn();
    const setActiveTab = vi.fn();
    const navigate = vi.fn();

    const Harness = () => {
      useRegistrarHotkeys({
        setShowWizard,
        setShowSlotsModal,
        setActiveTab,
        navigate,
        showWizard: true,
        showSlotsModal: false,
        appointments: [],
      });
      return null;
    };
    render(<Harness />);

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(setShowWizard).not.toHaveBeenCalled();
  });
});
