import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import Modal from '../Modal';

vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light' }),
}));

vi.mock('@/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

it('preserves the focused control on close callback updates and restores the trigger on close', async () => {
  const originalClose = vi.fn();
  const currentClose = vi.fn();
  const content = (open: boolean, onClose: () => void) => (
    <>
      <input aria-label="Background field" />
      <Modal isOpen={open} onClose={onClose} title="Synthetic confirmation" size="small">
        <button type="button">Cancel</button>
        <button type="button">Confirm</button>
      </Modal>
    </>
  );
  const view = render(content(false, originalClose));
  const trigger = screen.getByRole('textbox', { name: 'Background field' });
  trigger.focus();
  view.rerender(content(true, originalClose));

  const dialog = screen.getByRole('dialog', { name: 'Synthetic confirmation' });
  await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
  const confirm = screen.getByRole('button', { name: 'Confirm' });
  confirm.focus();

  view.rerender(content(true, currentClose));
  expect(confirm).toHaveFocus();
  fireEvent.keyDown(confirm, { key: 'Escape' });
  expect(currentClose).toHaveBeenCalledOnce();
  expect(originalClose).not.toHaveBeenCalled();

  view.rerender(content(false, currentClose));
  expect(trigger).toHaveFocus();
});
