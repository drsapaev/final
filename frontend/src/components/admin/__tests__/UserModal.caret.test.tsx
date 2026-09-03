/**
 * Regression: the caret died after every typed character in the admin
 * user form. Root cause — ErrorMessage and FormField were defined INSIDE
 * the UserModal render body, so each keystroke created fresh component
 * types and React remounted the whole subtree (inputs included),
 * destroying focus. The fix hoists them to module scope; this test pins
 * DOM-node identity across a keystroke.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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

vi.mock('../../roles/useRoles', () => ({
  useRoles: () => ({
    roleOptions: [
      { value: 'Admin', label: 'Admin' },
      { value: 'Doctor', label: 'Doctor' },
    ],
  }),
}));

import { ThemeProvider } from '@/contexts/ThemeContext';
import UserModal from '../UserModal';

afterEach(() => cleanup());

describe('UserModal caret regression (form components must not remount)', () => {
  it('keeps focus and the same input node across typed characters', () => {
    render(
      <ThemeProvider>
        <UserModal isOpen onClose={vi.fn()} onSave={onSave} />
      </ThemeProvider>,
    );

    const usernameInput = screen.getByPlaceholderText(
      'admin2.umdl_ph_username',
    ) as HTMLInputElement;
    usernameInput.focus();
    expect(document.activeElement).toBe(usernameInput);
    const nodeBefore = usernameInput;

    fireEvent.change(usernameInput, { target: { value: 'a' } });
    fireEvent.change(usernameInput, { target: { value: 'ab' } });

    // Value survives via controlled state…
    expect(screen.getByPlaceholderText('admin2.umdl_ph_username')).toHaveValue('ab');
    // …and the SAME DOM node is still focused (previously it was remounted).
    const nodeAfter = screen.getByPlaceholderText(
      'admin2.umdl_ph_username',
    ) as HTMLInputElement;
    expect(nodeAfter).toBe(nodeBefore);
    expect(document.activeElement).toBe(nodeAfter);
  });
});
