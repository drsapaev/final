/**
 * Fix A — safe patient identity & selection in AppointmentWizardV2.
 *
 * Audit findings (isolated checks #3, #7 + static): (a) editing the FIO
 * after selecting an existing card cleared only patient.id while keeping
 * phone/address/birth date/gender/name fields of the previous person —
 * mixed identities in one record; (b) ANY HTTP 400 during patient creation
 * with a phone present was treated as "phone already exists" and the wizard
 * silently auto-assigned whichever card matched the phone digits.
 *
 * Fix A contract:
 *  - typing in the search field = starting a new patient: the whole
 *    inherited card (id + demographics) is cleared synchronously;
 *  - duplicate-phone is recognized ONLY by the machine-readable error code
 *    `patient_phone_exists` (backend structured detail) and results in an
 *    explicit "select this card" offer — never an automatic re-target;
 *  - any other 400 is a validation error with no phone lookup.
 *
 * These tests mount the real wizard with the API layer mocked.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../../test/renderWithProviders';

// vi.hoisted so the hoisted vi.mock factory can reference the fixtures.
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
    id: 'card-A',
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

let createPatientResponse: () => Promise<unknown> = async () => ({ id: 'p-new', full_name: 'Тестов Тест Тестович' });
const phoneSearchCalls: string[] = [];
type Pending = { query: string; resolve: (v: unknown) => void; reject: (e: unknown) => void };
const pendingSearches: Pending[] = [];
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const waitForPending = async (arr: Pending[], count: number) => {
  for (let i = 0; i < 30; i++) {
    if (arr.length >= count) return;
    await sleep(50);
  }
  expect(arr.length).toBe(count);
};

vi.mock('../../../api/patients', () => ({
  getPatient: vi.fn(),
  createPatient: vi.fn(() => createPatientResponse()),
  updatePatient: vi.fn().mockResolvedValue({ id: 'x' }),
  searchPatientsByPhone: vi.fn((phone: string) => {
    phoneSearchCalls.push(phone);
    return Promise.resolve([]);
  }),
  searchPatients: vi.fn((query: string) =>
    new Promise((resolve, reject) => {
      pendingSearches.push({ query, resolve: (v: unknown) => { console.log('MOCK-A resolve', query); resolve(v); }, reject });
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

import AppointmentWizardV2 from '../AppointmentWizardV2';
import {
  createPatient,
  createRegistrarCart,
  findPatientByPhoneVariants,
} from '../../../api/patients';

// Emulates the REAL api/patients.createPatient error contract after Fix A:
// the adapter parses the structured backend detail and rethrows an Error
// carrying .status, .code and a human-readable .message.
const apiCreateError = (code: string, message: string): Error => {
  const err = new Error(message) as Error & { status?: number; code?: string; detail?: string };
  err.status = 400;
  err.code = code;
  err.detail = message;
  return err;
};

// Typed handles over the module mocks.
const createPatientMock = vi.mocked(createPatient);
const createRegistrarCartMock = vi.mocked(createRegistrarCart);
const findByPhoneMock = vi.mocked(findPatientByPhoneVariants);

const noop = () => {};
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

const getFio = () => screen.getByPlaceholderText('Введите ФИО для поиска или создания') as HTMLInputElement;
const getPhone = () => screen.getByPlaceholderText('+998 XX XXX XX XX') as HTMLInputElement;

beforeEach(() => {
  vi.clearAllMocks();
  phoneSearchCalls.length = 0;
  pendingSearches.length = 0;
  createPatientResponse = async () => ({ id: 'p-new', full_name: 'Тестов Тест Тестович' });
  findByPhoneMock.mockResolvedValue(null);
});

afterEach(() => {
  document.body.innerHTML = '';
});

/** Fill step 1 with a fresh (non-existent) patient and advance to the cart. */
const fillStep1 = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.type(getFio(), 'Тестов Тест Тестович');
  await user.type(getPhone(), '+998 90 999 88 77');
  const group = screen.getByRole('radiogroup');
  group.focus();
  await user.keyboard('{ArrowRight}');
  // Step 1 has no address required; advance via the "Далее" button (a click,
  // not Enter-on-button, to stay independent of keyboard-handling fixes).
  await user.click(screen.getByRole('button', { name: 'Далее' }));
  await waitFor(() => { expect(screen.getByText(/Консультация кардиолога/)).toBeTruthy(); }, { timeout: 2000 });
};

/** Add the service to the cart and submit through the confirm dialog. */
const submitCart = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('checkbox', { name: /Select as SelectRaw service Консультация кардиолога/ }));
  await user.click(screen.getByRole('button', { name: 'Завершить' }));
  // Summary confirmation dialog.
  await user.click(await screen.findByRole('button', { name: 'Создать' }, { timeout: 2000 }));
  await new Promise((r) => setTimeout(r, 30));
};

describe('Fix A: identity is not mixed when starting a new search', () => {
  it('clears all inherited demographics when the FIO text changes after selecting a card', async () => {
    const user = userEvent.setup();
    renderWizard();

    // Select an existing card from suggestions.
    fireEvent.change(getFio(), { target: { value: 'Существов' } });
    await waitForPending(pendingSearches, 1);
    pendingSearches[0].resolve([existingCard]);
    await waitFor(() => {
      expect(screen.getAllByText(/Существов Иван Иванович/).length).toBeGreaterThan(0);
    }, { timeout: 2000 });
    fireEvent.click(screen.getByRole('button', { name: /Существов Иван Иванович/ }));

    // Card data is populated.
    expect((getPhone() as HTMLInputElement).value).toBe('+998901111111');

    // User edits the FIO text → search mode: the whole card must reset.
    fireEvent.change(getFio(), { target: { value: 'Тестов' } });

    expect((getFio() as HTMLInputElement).value).toBe('Тестов');
    expect((getPhone() as HTMLInputElement).value).toBe('');
    expect((screen.getByPlaceholderText('Адрес проживания') as HTMLInputElement).value).toBe('');
    // Gender radio group has no selection anymore.
    const group = screen.getByRole('radiogroup');
    const checked = group.querySelector('[aria-checked="true"]');
    expect(checked).toBeNull();
  });
});

describe('Fix A: duplicate-phone 400 requires explicit card selection', () => {
  it('does NOT auto-assign the phone-matched card; offers explicit selection instead', async () => {
    const user = userEvent.setup();
    createPatientResponse = async () => {
      throw apiCreateError('patient_phone_exists', 'Пациент с таким номером телефона уже существует');
    };
    findByPhoneMock.mockResolvedValue(existingCard as never);

    renderWizard();
    await fillStep1(user);
    await submitCart(user);

    // The cart must NOT be created for an auto-picked patient.
    await waitFor(() => {
      expect(createRegistrarCartMock).not.toHaveBeenCalled();
    }, { timeout: 2000 });

    // The wizard is back on step 1 with the explicit choice offer.
    await waitFor(() => {
      expect(screen.getByText(/Выберите его карточку ниже или очистите телефон/)).toBeTruthy();
    }, { timeout: 2000 });
    const chooseButton = screen.getByRole('button', { name: /Выбрать Существов Иван Иванович/ });
    expect(chooseButton).toBeTruthy();

    // Explicit selection replaces the whole card data set.
    await user.click(chooseButton);
    expect((getFio() as HTMLInputElement).value).toBe('Существов Иван Иванович');
    expect((getPhone() as HTMLInputElement).value).toBe('+998901111111');
  });

  it('aborts the submit when the duplicate-phone card cannot be resolved', async () => {
    const user = userEvent.setup();
    createPatientResponse = async () => {
      throw apiCreateError('patient_phone_exists', 'Пациент с таким номером телефона уже существует');
    };
    findByPhoneMock.mockResolvedValue(null);

    renderWizard();
    await fillStep1(user);
    await submitCart(user);

    await waitFor(() => {
      expect(createRegistrarCartMock).not.toHaveBeenCalled();
    }, { timeout: 2000 });
    // No auto-selection happened: the wizard stays on the patient step
    // with a fresh (id-less) card and the duplicate-phone warning.
    expect(screen.getByText('Пациент с таким номером уже существует')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Выбрать/ })).toBeNull();
  });
});

describe('Fix A: any other 400 is a validation error, not a phone match', () => {
  it('does not run a phone lookup and does not offer card selection', async () => {
    const user = userEvent.setup();
    createPatientResponse = async () => {
      throw apiCreateError('patient_name_invalid', 'Некорректное ФИО');
    };

    renderWizard();
    await fillStep1(user);
    await submitCart(user);

    await waitFor(() => {
      expect(createRegistrarCartMock).not.toHaveBeenCalled();
    }, { timeout: 2000 });
    // The duplicate-phone flow was not triggered at all.
    expect(findByPhoneMock).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /Выбрать/ })).toBeNull();
  });
});

describe('Fix A: unique phone still creates a new patient normally', () => {
  it('creates the patient and submits the cart with the created id', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillStep1(user);
    await submitCart(user);

    await waitFor(() => {
      expect(createRegistrarCartMock).toHaveBeenCalledTimes(1);
    }, { timeout: 2000 });
    const cartPayload = createRegistrarCartMock.mock.calls[0][0] as Record<string, unknown>;
    expect(cartPayload.patient_id).toBe('p-new');
  });
});
