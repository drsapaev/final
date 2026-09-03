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
      data: [{ code: 'cardiology' }, { code: 'dermatology' }, { code: 'dentistry' }],
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

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import { ThemeProvider } from '@/contexts/ThemeContext';
import UserModal from '../UserModal';

afterEach(() => {
  cleanup();
  onSave.mockClear();
  vocabularyShouldFail = false;
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
    const option = await screen.findByRole('option', {
      name: 'admin2.umdl_spec_cardiology',
    });
    expect(option).toBeTruthy();
  });
});
