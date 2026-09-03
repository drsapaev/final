/**
 * Regression (Sentry PYTHON-FASTAPI-M): the admin add-user form sent
 * `role` as the macos Select's legacy event-like object
 * ({ target: { value: '…' } }) instead of the plain string that
 * UserCreateRequest.role expects, so POST /api/v1/users/users always
 * failed with 422. The fix switches the role Select to onValueChange;
 * this test pins the payload shape.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const onSave = vi.fn().mockResolvedValue(undefined);

vi.mock('../../../api/client', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn(),
  },
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

// NOTE: no useRoles mock — the real hook runs against the mocked api client,
// gets [], and UserModal falls back to its static role list where option
// labels are raw i18n keys (t is identity-mocked).

import { ThemeProvider } from '@/contexts/ThemeContext';
import UserModal from '../UserModal';

afterEach(() => cleanup());

describe('UserModal role payload regression', () => {
  it('sends role as a plain string after selecting from the dropdown', async () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );

    fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_username'), {
      target: { value: 'registrar' },
    });
    fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_email'), {
      target: { value: 'registrar@clinic.test' },
    });
    fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_password'), {
      target: { value: 'StrongPass123' },
    });
    fireEvent.change(screen.getByPlaceholderText('admin2.umdl_ph_password_confirm'), {
      target: { value: 'StrongPass123' },
    });

    // Open the role Select (single macos Select in the modal) and pick a role
    const selectTrigger = screen
      .getAllByRole('button')
      .find((el) => el.getAttribute('aria-haspopup') === 'listbox');
    expect(selectTrigger).toBeDefined();
    fireEvent.click(selectTrigger as HTMLElement);

    const options = await screen.findAllByRole('option');

    // REC-1 (Receptionist deprecation): 'Receptionist' is frozen out of the
    // create-role options — Registrar is the canonical front-desk role.
    // This absence assertion is the frontend write-freeze contract.
    expect(options.find((el) => el.textContent === 'admin2.umdl_role_receptionist')).toBeUndefined();

    // M-1 (Manager deprecation): 'Manager' is frozen out of the create-role
    // options — it is a deprecated legacy/synthetic role, not a product role.
    // Absence assertion = frontend write-freeze contract (fallback list);
    // the API-driven path is covered by the backend write-pattern tests.
    expect(options.find((el) => el.textContent === 'admin2.umdl_role_manager')).toBeUndefined();

    const option = options.find((el) => el.textContent === 'admin2.umdl_role_registrar');
    expect(option).toBeDefined();
    fireEvent.click(option as HTMLElement);

    fireEvent.submit(screen.getByRole('button', { name: 'Create user' }).closest('form')!);

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const payload = onSave.mock.calls[0][0] as Record<string, unknown>;
    expect(payload.role).toBe('Registrar');
  });
});
