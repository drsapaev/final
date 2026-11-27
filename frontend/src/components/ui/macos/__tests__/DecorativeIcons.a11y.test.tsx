import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import Alert from '../Alert';
import Modal from '../Modal';
import Select from '../Select';

vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light' }),
}));

vi.mock('@/i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string) => key === 'common.close' ? 'Закрыть' : key,
  }),
}));

it('keeps the alert text accessible without exposing the decorative severity icon', () => {
  render(<Alert type="warning" title="Synthetic warning" description="Check the form" />);
  const alert = screen.getByRole('alert');
  expect(alert).toHaveTextContent('Synthetic warning');
  expect(alert).toHaveTextContent('Check the form');
  expect(alert.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  expect(alert.querySelector('svg')).toHaveAttribute('focusable', 'false');
});

it('keeps the select arrow hidden and out of focus while allowing selection', () => {
  const onValueChange = vi.fn();
  render(<Select placeholder="Choose a value" options={['First']} onValueChange={onValueChange} />);
  const trigger = screen.getByRole('button', { name: 'Choose a value' });
  expect(trigger.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  expect(trigger.querySelector('svg')).toHaveAttribute('focusable', 'false');
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole('option', { name: 'First' }));
  expect(onValueChange).toHaveBeenCalledWith('First');
});

it('uses a localized fullscreen close button with a hidden glyph and no duplicate accessible description', () => {
  const onClose = vi.fn();
  render(<Modal isOpen onClose={onClose} size="fullscreen" closeOnBackdrop={false} title="Synthetic dialog">Content</Modal>);
  const dialog = screen.getByRole('dialog', { name: 'Synthetic dialog' });
  const close = within(dialog).getAllByRole('button', { name: 'Закрыть' }).find((control) => control.tagName === 'BUTTON');
  if (!close) throw new Error('Fullscreen close button not found');
  expect(close).not.toHaveAccessibleDescription();
  expect(close).not.toHaveAttribute('title');
  expect(within(close).getByText('✕')).toHaveAttribute('aria-hidden', 'true');
  fireEvent.click(close);
  expect(onClose).toHaveBeenCalledOnce();
});
