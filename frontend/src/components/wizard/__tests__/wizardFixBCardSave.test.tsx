/**
 * Fix B — explicit, verifiable persistence of patient-card edits.
 *
 * Audit findings: on the ordinary existing-patient path the form allowed
 * editing phone/address/birth date, but the cart was created with
 * patient_id alone — edits were silently discarded; and the edit-mode
 * update path sent `full_name`, which PatientUpdate does not accept
 * (silently dropped with a 200 response).
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { splitFioForUpdate } from '../wizardUtils';

const { service, existingCard } = vi.hoisted(() => ({
  service: {
    id: 'svc-1',
    name: 'Консультация кардиолога',
    price: 100000,
    service_code: 'K1',
    category_code: 'K',
    is_consultation: true,
    requires_doctor: false,
  },
  existingCard: {
    id: 'card-B',
    fio: 'Существов Иван Иванович',
    last_name: 'Существов',
    first_name: 'Иван',
    middle_name: 'Иванович',
    phone: '+998901111111',
    address: 'ул. Старая 1',
    birth_date: '1980-01-01',
    sex: 'M',
  },
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: vi.fn().mockResolvedValue({
      data: { services_by_group: { g1: [service] }, doctors: [], queue_profiles: [] },
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
  buildApiUrl: (p: string) => `http://test${p}`,
  buildWsUrl: (p: string) => `ws://test${p}`,
  default: {},
}));

// Server-side card state used by the getPatient read-back mock.
const serverCard: Record<string, unknown> = { ...existingCard };
let updateBehavior: 'ok' | 'reject' = 'ok';

vi.mock('../../../api/patients', () => ({
  getPatient: vi.fn(() => Promise.resolve({ ...serverCard })),
  createPatient: vi.fn(),
  updatePatient: vi.fn((_id: unknown, payload: Record<string, unknown>) => {
    if (updateBehavior === 'reject') {
      const err = new Error('Ошибка обновления пациента (400)') as Error & { status?: number };
      err.status = 400;
      return Promise.reject(err);
    }
    return Promise.resolve({ id: 'card-B', ...payload });
  }),
  searchPatientsByPhone: vi.fn().mockResolvedValue([]),
  searchPatients: vi.fn((query: string) =>
    new Promise((resolve, reject) => {
      pendingSearches.push({ query, resolve: (v: unknown) => { void query; resolve(v); }, reject });
    })),
  checkAuthProbe: vi.fn().mockResolvedValue(true),
  createRegistrarCart: vi.fn().mockResolvedValue({ success: true, total_amount: 100000 }),
  findPatientByPhoneVariants: vi.fn().mockResolvedValue(null),
}));

vi.mock('../../../utils/tokenManager', () => ({
  default: {
    getAccessToken: vi.fn().mockReturnValue('test-token'),
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
  },
}));

type Pending = { query: string; resolve: (v: unknown) => void; reject: (e: unknown) => void };
const pendingSearches: Pending[] = [];

import AppointmentWizardV2 from '../AppointmentWizardV2';
import { createRegistrarCart, getPatient, updatePatient } from '../../../api/patients';

const updatePatientMock = vi.mocked(updatePatient);
const getPatientMock = vi.mocked(getPatient);
const createCartMock = vi.mocked(createRegistrarCart);

const noop = () => {};
const getFio = () => screen.getByPlaceholderText('Введите ФИО для поиска или создания') as HTMLInputElement;
const getPhone = () => screen.getByPlaceholderText('+998 XX XXX XX XX') as HTMLInputElement;
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

const seedRegistrarProfile = () => {
  window.sessionStorage.setItem(
    'auth_profile',
    JSON.stringify({ id: 1, username: 'test-registrar', role: 'Registrar' })
  );
};

const renderWizard = () => {
  seedRegistrarProfile();
  return renderWithProviders(
    <AppointmentWizardV2 isOpen onClose={noop} onComplete={noop} />
  );
};

const selectExistingCard = async () => {
  fireEvent.change(getFio(), { target: { value: 'Существов' } });
  // Wait for the debounced search call, then resolve it from the test
  // (act-free pattern: timer-driven updates stay deferred otherwise).
  for (let i = 0; i < 30 && pendingSearches.length === 0; i++) {
    await sleep(50);
  }
  expect(pendingSearches.length).toBe(1);
  pendingSearches[0].resolve([existingCard]);
  await waitFor(() => {
    expect(screen.getAllByText(/Существов Иван Иванович/).length).toBeGreaterThan(0);
  }, { timeout: 2000 });
  fireEvent.click(screen.getByRole('button', { name: /Существов Иван Иванович/ }));
};

const fillAndSubmit = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: 'Далее' }));
  await waitFor(() => {
    expect(screen.getByText(/Консультация кардиолога/)).toBeTruthy();
  }, { timeout: 2000 });
  await user.click(screen.getByRole('checkbox', { name: /Select as SelectRaw service Консультация кардиолога/ }));
  await user.click(screen.getByRole('button', { name: 'Завершить' }));
  await user.click(await screen.findByRole('button', { name: 'Создать' }, { timeout: 2000 }));
  await sleep(30);
};

beforeEach(() => {
  vi.clearAllMocks();
  Object.assign(serverCard, existingCard);
  updateBehavior = 'ok';
  pendingSearches.length = 0;
});

afterEach(() => {
  document.body.innerHTML = '';
});

describe('splitFioForUpdate (Fix B: PatientUpdate DTO contract)', () => {
  it('splits FIO into separate name fields (no full_name key)', () => {
    const result = splitFioForUpdate('Существов Иван Иванович');
    expect(result).toEqual({ last_name: 'Существов', first_name: 'Иван', middle_name: 'Иванович' });
    expect('full_name' in result).toBe(false);
  });

  it('falls back to last name only', () => {
    expect(splitFioForUpdate('Ахмедов')).toEqual({ last_name: 'Ахмедов', first_name: 'Ахмедов' });
    expect(splitFioForUpdate('')).toEqual({});
  });
});

describe('Fix B: explicit card persistence on the ordinary path', () => {
  it('persists edited demographics with read-back verification and creates the cart', async () => {
    const user = userEvent.setup();
    renderWizard();

    await selectExistingCard();
    expect((getPhone() as HTMLInputElement).value).toBe('+998901111111');

    // Edit the phone (and only the phone). Read-back returns the UPDATED card.
    fireEvent.change(getPhone(), { target: { value: '+998 90 999 88 77' } });
    serverCard.phone = '+998909998877';

    await fillAndSubmit(user);

    expect(updatePatientMock).toHaveBeenCalledTimes(1);
    const [pid, payload] = updatePatientMock.mock.calls[0];
    expect(pid).toBe('card-B');
    expect(String((payload as Record<string, unknown>).phone).replace(/\D/g, '')).toBe('998909998877');
    expect((payload as Record<string, unknown>).address).toBeUndefined();
    expect((payload as Record<string, unknown>).birth_date).toBeUndefined();

    // Read-back verification happened.
    expect(getPatientMock).toHaveBeenCalledWith('card-B');

    // The cart was created.
    expect(createCartMock).toHaveBeenCalledTimes(1);
  });

  it('does not send an update request when the card is unchanged', async () => {
    const user = userEvent.setup();
    renderWizard();

    await selectExistingCard();
    await fillAndSubmit(user);

    expect(updatePatientMock).not.toHaveBeenCalled();
    expect(getPatientMock).not.toHaveBeenCalled();
    expect(createCartMock).toHaveBeenCalledTimes(1);
  });

  it('aborts the submission when a 200 update did not actually persist', async () => {
    const user = userEvent.setup();
    renderWizard();

    await selectExistingCard();
    fireEvent.change(getPhone(), { target: { value: '+998 90 999 88 77' } });
    // Server answers 200 but the read-back shows the OLD phone.
    serverCard.phone = '+998901111111';

    await fillAndSubmit(user);

    expect(updatePatientMock).toHaveBeenCalledTimes(1);
    expect(getPatientMock).toHaveBeenCalledTimes(1);
    expect(createCartMock).not.toHaveBeenCalled();
  });

  it('aborts the submission and shows no success when the update fails', async () => {
    const user = userEvent.setup();
    renderWizard();

    await selectExistingCard();
    fireEvent.change(getPhone(), { target: { value: '+998 90 999 88 77' } });
    updateBehavior = 'reject';

    await fillAndSubmit(user);

    expect(updatePatientMock).toHaveBeenCalledTimes(1);
    expect(createCartMock).not.toHaveBeenCalled();
  });
});
