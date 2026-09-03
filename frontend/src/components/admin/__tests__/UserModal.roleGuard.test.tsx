/**
 * Codex round-5 regression guards for the doctor onboarding modal:
 *
 * 1. Bare lowercase "doctor" (a backend compatibility spelling accepted by
 *    NonDoctorUserCreateRequest with NO linked Doctor profile —
 *    DOCTOR_PROFILE_ROLES excludes it) must never be offered in create mode;
 *    the canonical exact "Doctor" stays selectable and legacy spellings stay
 *    selectable in edit mode (no hidden role migration on plain save).
 *
 * 2. A failed GET /admin/doctors/specialty-vocabulary must surface a visible
 *    error with a localized retry action instead of silently leaving an
 *    empty specialty select that blocks onboarding.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const onSave = vi.fn().mockResolvedValue(undefined);

let vocabularyShouldFail = false;

const apiGet = vi.fn().mockImplementation((url: string) => {
  if (url === '/roles/options') {
    return Promise.resolve({
      data: {
        options: [
          { value: 'Admin', label: 'Администратор' },
          { value: 'Doctor', label: 'Врач' },
          { value: 'doctor', label: 'doctor' },
          { value: 'Nurse', label: 'Медсестра' },
        ],
      },
    });
  }
  if (url === '/admin/doctors/specialty-vocabulary') {
    if (vocabularyShouldFail) {
      return Promise.reject(new Error('vocabulary unavailable'));
    }
    return Promise.resolve({
      data: [
        { code: 'cardiology', title_ru: 'Кардиология', title_uz: 'Kardiologiya', title_en: 'Cardiology' },
        { code: 'dermatology', title_ru: 'Дерматология', title_uz: 'Dermatologiya', title_en: 'Dermatology' },
        { code: 'dentistry', title_ru: 'Стоматология', title_uz: 'Stomatologiya', title_en: 'Dentistry' },
      ],
    });
  }
  return Promise.resolve({ data: [] });
});

vi.mock('../../../api/client', () => ({
  api: {
    get: (...args: unknown[]) => apiGet(...(args as [string])),
    post: vi.fn(),
  },
}));

const i18nState = vi.hoisted(() => ({ locale: 'ru' }));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string) =>
      i18nState.locale === 'ru' ? key : `${key}@${i18nState.locale}`,
  }),
}));

import { ThemeProvider } from '@/contexts/ThemeContext';
import UserModal from '../UserModal';

afterEach(() => {
  cleanup();
  onSave.mockClear();
  vocabularyShouldFail = false;
  i18nState.locale = 'ru';
  apiGet.mockClear();
});

const openRoleSelect = async () => {
  const selectTrigger = screen
    .getAllByRole('button')
    .find((el) => el.getAttribute('aria-haspopup') === 'listbox');
  fireEvent.click(selectTrigger as HTMLElement);
  return screen.findAllByRole('option');
};

const pickDoctorRole = async () => {
  const options = await openRoleSelect();
  const doctor = options.find((el) => el.textContent === 'Врач');
  expect(doctor).toBeDefined();
  fireEvent.click(doctor as HTMLElement);
};

describe('UserModal legacy doctor-role guard (create mode)', () => {
  it('hides the bare lowercase "doctor" compatibility value, keeps canonical "Doctor"', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    const options = await openRoleSelect();
    const values = options.map((el) => el.textContent);
    expect(values).not.toContain('doctor');
    expect(values).toContain('Врач'); // canonical exact "Doctor"
    expect(values).not.toContain('admin2.umdl_role_doctor_general'); // fallback list not merged
  });

  it('keeps the user legacy role selectable in edit mode (no hidden migration)', async () => {
    render(
      <ThemeProvider>
        <UserModal
          isOpen
          onClose={vi.fn()}
          onSave={onSave}
          user={{ username: 'legacy_doc', role: 'doctor', is_active: true }}
        />
      </ThemeProvider>,
    );
    const options = await openRoleSelect();
    expect(options.map((el) => el.textContent)).toContain('doctor');
  });
});

describe('UserModal specialty vocabulary load failure', () => {
  it('reports the failure with a retry action that reloads the vocabulary', async () => {
    vocabularyShouldFail = true;
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    await pickDoctorRole();
    const error = await screen.findByText('admin2.umdl_spec_load_error');
    expect(error).toBeTruthy();
    const retry = screen.getByRole('button', { name: 'admin2.umdl_spec_retry' });
    expect(retry).toBeTruthy();

    const vocabCalls = () =>
      apiGet.mock.calls.filter(([url]) => url === '/admin/doctors/specialty-vocabulary').length;
    expect(vocabCalls()).toBe(1);

    vocabularyShouldFail = false;
    fireEvent.click(retry);
    expect(vocabCalls()).toBe(2);
    await waitFor(() => {
      expect(screen.queryByText('admin2.umdl_spec_load_error')).toBeNull();
    });
    // open the specialty dropdown (the second listbox trigger) to verify the
    // reloaded vocabulary actually populated the options
    const triggers = screen
      .getAllByRole('button')
      .filter((el) => el.getAttribute('aria-haspopup') === 'listbox');
    fireEvent.click(triggers[triggers.length - 1] as HTMLElement);
    // ru locale: the mocked t() returns the key itself (no umdl_spec_*
    // resources) → the label falls back to the locale catalog title.
    const option = await screen.findByRole('option', {
      name: 'Кардиология',
    });
    expect(option).toBeTruthy();
  });
});

describe('UserModal codex round-6 follow-ups', () => {
  it('recomputes specialty labels when the interface locale changes while the modal is open', async () => {
    const view = render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    await pickDoctorRole();
    // open the specialty dropdown (the last listbox trigger) and check the
    // label in the initial locale
    const triggers = screen
      .getAllByRole('button')
      .filter((el) => el.getAttribute('aria-haspopup') === 'listbox');
    fireEvent.click(triggers[triggers.length - 1] as HTMLElement);
    expect(
      await screen.findByRole('option', { name: 'Кардиология' }),
    ).toBeTruthy();

    // switch locale while the modal stays open -> a locale change re-renders
    // the modal and labels re-resolve at render time without a refetch
    i18nState.locale = 'en';
    view.rerender(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    // the dropdown stays open across the re-render (Select keeps its own
    // open state) — options must now carry re-resolved labels
    expect(
      await screen.findByRole('option', {
        name: 'admin2.umdl_spec_cardiology@en',
      }),
    ).toBeTruthy();
  });

  it('blocks a price beyond the Numeric(10,2) column precision and accepts the boundary value', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    await pickDoctorRole();
    fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_username'), {
      target: { value: 'doctor_price' },
    });
    fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_email'), {
      target: { value: 'doctor.price@clinic.test' },
    });
    fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_password'), {
      target: { value: 'StrongPass123' },
    });
    fireEvent.change(
      screen.getByPlaceholderText('admin2.umdl_ph_password_confirm'),
      { target: { value: 'StrongPass123' } },
    );

    const specialtyTriggers = screen
      .getAllByRole('button')
      .filter((el) => el.getAttribute('aria-haspopup') === 'listbox');
    fireEvent.click(specialtyTriggers[specialtyTriggers.length - 1] as HTMLElement);
    const spec = await screen.findByRole('option', {
      name: 'Кардиология',
    });
    fireEvent.click(spec);

    // oversized value: 9 integer digits -> field error, submit blocked
    fireEvent.change(screen.getByPlaceholderText('150000'), {
      target: { value: '100000000' },
    });
    fireEvent.submit(
      screen.getByRole('button', { name: 'Create user' }).closest('form')!,
    );
    expect(
      await screen.findByText('admin2.umdl_err_doctor_price_max'),
    ).toBeTruthy();
    expect(onSave).not.toHaveBeenCalled();

    // boundary value: exactly Numeric(10,2) max -> submits
    fireEvent.change(screen.getByPlaceholderText('150000'), {
      target: { value: '99999999.99' },
    });
    fireEvent.submit(
      screen.getByRole('button', { name: 'Create user' }).closest('form')!,
    );
    await waitFor(() => expect(onSave).toHaveBeenCalled());
  });
});
