/**
 * Canonical doctor onboarding (owner decision 2026-09-01):
 * creating a system doctor is ONE operation in the Users module —
 * role=Doctor reveals the mandatory "Doctor profile" block, and the
 * payload must carry doctor_profile with a canonical specialty.
 * Legacy doctor-role spellings (cardio/derma/dentist) must not be
 * offered when creating a user.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const onSave = vi.fn().mockResolvedValue(undefined);

const apiGet = vi.fn().mockImplementation((url: string) => {
  if (url === '/admin/doctors/specialty-vocabulary') {
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
});

const openRoleSelect = async () => {
  const selectTrigger = screen
    .getAllByRole('button')
    .find((el) => el.getAttribute('aria-haspopup') === 'listbox');
  fireEvent.click(selectTrigger as HTMLElement);
  return screen.findAllByRole('option');
};

const fillBaseUserForm = () => {
  fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_username'), {
    target: { value: 'doctor_onboard' },
  });
  fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_email'), {
    target: { value: 'doctor.onboard@clinic.test' },
  });
  fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_password'), {
    target: { value: 'StrongPass123' },
  });
  fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_password_confirm'), {
    target: { value: 'StrongPass123' },
  });
};

const submitForm = () =>
  fireEvent.submit(screen.getByRole('button', { name: 'Create user' }).closest('form')!);

describe('UserModal doctor onboarding', () => {
  it('shows the doctor profile block only for role=Doctor in create mode', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    expect(screen.queryByText('admin2.umdl_doctor_profile_section')).toBeNull();

    const options = await openRoleSelect();
    const doctor = options.find((el) => el.textContent === 'admin2.umdl_role_doctor_general');
    expect(doctor).toBeDefined();
    fireEvent.click(doctor as HTMLElement);

    await waitFor(() =>
      expect(screen.getByText('admin2.umdl_doctor_profile_section')).toBeDefined(),
    );
  });

  it('does not offer legacy doctor-role spellings in create mode', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    const options = await openRoleSelect();
    const labels = options.map((el) => el.textContent);
    expect(labels).not.toContain('admin2.umdl_role_cardio');
    expect(labels).not.toContain('admin2.umdl_role_derma');
    expect(labels).not.toContain('admin2.umdl_role_dentist');
  });

  it('blocks submit until a specialty is selected', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    fillBaseUserForm();
    const options = await openRoleSelect();
    fireEvent.click(options.find((el) => el.textContent === 'admin2.umdl_role_doctor_general') as HTMLElement);
    await waitFor(() =>
      expect(screen.getByText('admin2.umdl_doctor_profile_section')).toBeDefined(),
    );

    submitForm();
    await waitFor(() =>
      expect(screen.getByText('admin2.umdl_err_doctor_specialty_required')).toBeDefined(),
    );
    expect(onSave).not.toHaveBeenCalled();
  });

  it('sends doctor_profile with the selected specialty', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    fillBaseUserForm();
    const options = await openRoleSelect();
    fireEvent.click(options.find((el) => el.textContent === 'admin2.umdl_role_doctor_general') as HTMLElement);
    await waitFor(() =>
      expect(screen.getByText('admin2.umdl_doctor_profile_section')).toBeDefined(),
    );

    // Specialty select appears after the role select; reopen the listbox.
    const specialtyTrigger = screen
      .getAllByRole('button')
      .filter((el) => el.getAttribute('aria-haspopup') === 'listbox')
      .pop() as HTMLElement;
    fireEvent.click(specialtyTrigger);
    const specialtyOptions = await screen.findAllByRole('option');
    fireEvent.click(
      specialtyOptions.find((el) => el.textContent === 'admin2.umdl_spec_cardiology') as HTMLElement,
    );

    submitForm();
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const payload = onSave.mock.calls[0][0] as {
      role: string;
      doctor_profile?: { specialty: string };
    };
    expect(payload.role).toBe('Doctor');
    expect(payload.doctor_profile?.specialty).toBe('cardiology');
  });

  it('never attaches doctor_profile for non-doctor roles', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    fillBaseUserForm();
    const options = await openRoleSelect();
    // REC-1: Receptionist is write-frozen — Registrar is the canonical
    // non-doctor role exercised here.
    fireEvent.click(options.find((el) => el.textContent === 'admin2.umdl_role_registrar') as HTMLElement);
    submitForm();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const payload = onSave.mock.calls[0][0] as Record<string, unknown>;
    expect(payload.doctor_profile).toBeUndefined();
  });
});

describe('UserModal onboarding numeric validation (Codex P2)', () => {
  const selectDoctorAndSpecialty = async () => {
    const roleTrigger = screen
      .getAllByRole('button')
      .find((el) => el.getAttribute('aria-haspopup') === 'listbox');
    fireEvent.click(roleTrigger as HTMLElement);
    const roleOptions = await screen.findAllByRole('option');
    fireEvent.click(
      roleOptions.find((el) => el.textContent === 'admin2.umdl_role_doctor_general') as HTMLElement,
    );
    await waitFor(() =>
      expect(screen.getByText('admin2.umdl_doctor_profile_section')).toBeDefined(),
    );
    const specialtyTrigger = screen
      .getAllByRole('button')
      .filter((el) => el.getAttribute('aria-haspopup') === 'listbox')
      .pop() as HTMLElement;
    fireEvent.click(specialtyTrigger);
    const specialtyOptions = await screen.findAllByRole('option');
    fireEvent.click(
      specialtyOptions.find((el) => el.textContent === 'admin2.umdl_spec_cardiology') as HTMLElement,
    );
  };

  const typeIntoField = (placeholder: string, value: string) => {
    fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value } });
  };

  it('rejects partially-numeric price input instead of truncating it', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    fillBaseUserForm();
    await selectDoctorAndSpecialty();
    typeIntoField('150000', '150abc');

    submitForm();
    await waitFor(() =>
      expect(screen.getByText('admin2.umdl_err_doctor_price_format')).toBeDefined(),
    );
    expect(onSave).not.toHaveBeenCalled();
  });

  it('accepts space-separated price and sends the normalized number', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    fillBaseUserForm();
    await selectDoctorAndSpecialty();
    typeIntoField('150000', '150 000');

    submitForm();
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const payload = onSave.mock.calls[0][0] as {
      doctor_profile?: { price_default?: number };
    };
    expect(payload.doctor_profile?.price_default).toBe(150000);
  });

  it.each(['abc', '12abc', '3.5', '0', '101'])(
    'rejects invalid online-limit value %s',
    async (bad) => {
      render(
        <ThemeProvider>
          <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
        </ThemeProvider>,
      );
      fillBaseUserForm();
      await selectDoctorAndSpecialty();
      typeIntoField('15', bad);

      submitForm();
      await waitFor(() =>
        expect(screen.getByText('admin2.umdl_err_doctor_number_range')).toBeDefined(),
      );
      expect(onSave).not.toHaveBeenCalled();
    },
  );

  it('sends strict integers for valid limit input', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );
    fillBaseUserForm();
    await selectDoctorAndSpecialty();
    typeIntoField('15', '20');

    submitForm();
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const payload = onSave.mock.calls[0][0] as {
      doctor_profile?: { max_online_per_day?: number };
    };
    expect(payload.doctor_profile?.max_online_per_day).toBe(20);
  });
});
