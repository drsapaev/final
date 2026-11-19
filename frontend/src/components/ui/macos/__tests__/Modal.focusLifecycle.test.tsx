import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Modal from '../Modal';

vi.mock('@/contexts/ThemeContext', () => ({ useTheme: () => ({}) }));
vi.mock('@/i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

function Fixture({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <>
      <button type="button">Open confirmation</button>
      <Modal isOpen={isOpen} onClose={onClose} title="Confirm changes">
        <input aria-label="Confirmation text" />
      </Modal>
    </>
  );
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

it('keeps focus inside an open dialog when the close callback changes', () => {
  const previousClose = vi.fn();
  const currentClose = vi.fn();
  const { rerender } = render(<Fixture isOpen={false} onClose={previousClose} />);
  const trigger = screen.getByRole('button', { name: 'Open confirmation' });
  trigger.focus();

  rerender(<Fixture isOpen onClose={previousClose} />);
  act(() => vi.advanceTimersByTime(32));
  const input = screen.getByRole('textbox', { name: 'Confirmation text' });
  input.focus();

  rerender(<Fixture isOpen onClose={currentClose} />);
  expect(input).toHaveFocus();
  act(() => vi.advanceTimersByTime(32));
  expect(input).toHaveFocus();

  fireEvent.keyDown(input, { key: 'Escape' });
  expect(currentClose).toHaveBeenCalledOnce();
  expect(previousClose).not.toHaveBeenCalled();

  rerender(<Fixture isOpen={false} onClose={currentClose} />);
  expect(trigger).toHaveFocus();
});
