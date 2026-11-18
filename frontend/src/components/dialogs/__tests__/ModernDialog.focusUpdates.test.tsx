import React, { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ModernDialog from '../ModernDialog';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const triggers: HTMLButtonElement[] = [];

const focusTrigger = () => {
  const trigger = document.createElement('button');
  trigger.textContent = 'Open synthetic editor';
  document.body.appendChild(trigger);
  trigger.focus();
  triggers.push(trigger);
  return trigger;
};

const finishInitialFocus = () => {
  act(() => vi.advanceTimersByTime(150));
};

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  for (const trigger of triggers.splice(0)) trigger.remove();
  vi.useRealTimers();
});

// AppointmentWizardV2 creates its customHeader JSX on every form update.
// Keep the real dialog here: mocking its wrapper hides the focus regression.
const ControlledEditor = () => {
  const [value, setValue] = useState('');
  return (
    <ModernDialog
      isOpen
      customHeader={<button type="button">Close synthetic editor</button>}
      ariaLabel="Synthetic editor"
    >
      <input
        aria-label="Synthetic field"
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
    </ModernDialog>
  );
};

describe('ModernDialog focus during form and prop updates', () => {
  it('allows continuous typing without refocusing after each fresh header', async () => {
    vi.useRealTimers();
    focusTrigger();
    const user = userEvent.setup();
    const settleFocus = async () => {
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 150));
      });
    };
    render(<ControlledEditor />);
    await settleFocus();
    const field = screen.getByRole('textbox', { name: 'Synthetic field' }) as HTMLInputElement;
    await user.click(field);

    let expected = '';
    for (const character of 'DEV-DEMO123') {
      await user.keyboard(character);
      expected += character;
      expect(field).toHaveFocus();
      expect(field).toHaveValue(expected);
      expect(field.selectionStart).toBe(expected.length);
      await settleFocus();
      expect(field).toHaveFocus();
      expect(field.selectionStart).toBe(expected.length);
    }
  });

  it('preserves the caret while header, title, and accessible name change', () => {
    focusTrigger();
    const editor = (version: number) => (
      <ModernDialog
        isOpen
        title={`Synthetic editor ${version}`}
        ariaLabel={`Synthetic label ${version}`}
        customHeader={<button type="button">Synthetic header {version}</button>}
      >
        <input aria-label="Synthetic field" defaultValue="SYNTHETIC-123" />
      </ModernDialog>
    );
    const { rerender } = render(editor(1));
    finishInitialFocus();
    const field = screen.getByRole('textbox', { name: 'Synthetic field' }) as HTMLInputElement;
    field.focus();
    field.setSelectionRange(3, 6);

    rerender(editor(2));

    expect(field).toHaveFocus();
    expect([field.selectionStart, field.selectionEnd]).toEqual([3, 6]);
    finishInitialFocus();
    expect(field).toHaveFocus();
    expect([field.selectionStart, field.selectionEnd]).toEqual([3, 6]);
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Synthetic editor 2');
  });

  it('restores focus inside the open dialog when a step replaces the focused field', () => {
    focusTrigger();
    const editor = (step: number) => (
      <ModernDialog
        isOpen
        ariaLabel="Synthetic step editor"
        customHeader={<button type="button">Synthetic step {step} action</button>}
      >
        <div key={step}>
          <input aria-label={`Synthetic step ${step} field`} />
        </div>
      </ModernDialog>
    );
    const { rerender } = render(editor(1));
    finishInitialFocus();
    const firstField = screen.getByRole('textbox', { name: 'Synthetic step 1 field' });
    firstField.focus();

    rerender(editor(2));

    expect(firstField.isConnected).toBe(false);
    expect(document.activeElement).toBe(document.body);
    finishInitialFocus();
    expect(screen.getByRole('button', { name: 'Synthetic step 2 action' })).toHaveFocus();
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement);
  });

  it('uses the latest Escape callback and option without disturbing focus', () => {
    focusTrigger();
    const oldClose = vi.fn();
    const newClose = vi.fn();
    const editor = (onClose: () => void, closeOnEscape: boolean) => (
      <ModernDialog isOpen title="Synthetic editor" onClose={onClose} closeOnEscape={closeOnEscape}>
        <input aria-label="Synthetic field" />
      </ModernDialog>
    );
    const { rerender } = render(editor(oldClose, true));
    finishInitialFocus();
    const field = screen.getByRole('textbox', { name: 'Synthetic field' });
    field.focus();

    rerender(editor(newClose, false));
    expect(field).toHaveFocus();
    fireEvent.keyDown(field, { key: 'Escape' });
    expect(oldClose).not.toHaveBeenCalled();
    expect(newClose).not.toHaveBeenCalled();

    rerender(editor(newClose, true));
    expect(field).toHaveFocus();
    fireEvent.keyDown(field, { key: 'Escape' });
    expect(newClose).toHaveBeenCalledTimes(1);
    expect(oldClose).not.toHaveBeenCalled();
    finishInitialFocus();
    expect(field).toHaveFocus();
  });

  it('keeps the inner dialog on top when the outer header rerenders', () => {
    focusTrigger();
    const closeOuter = vi.fn();
    const closeInner = vi.fn();
    const dialogs = (version: number) => (
      <>
        <ModernDialog
          isOpen
          onClose={closeOuter}
          ariaLabel="Outer synthetic editor"
          customHeader={<button type="button">Outer header {version}</button>}
        />
        <ModernDialog isOpen onClose={closeInner} title="Inner synthetic editor">
          <input aria-label="Inner synthetic field" />
        </ModernDialog>
      </>
    );
    const { rerender } = render(dialogs(1));
    finishInitialFocus();
    const field = screen.getByRole('textbox', { name: 'Inner synthetic field' });
    field.focus();

    rerender(dialogs(2));
    finishInitialFocus();
    expect(field).toHaveFocus();
    expect(document.body.style.overflow).toBe('hidden');

    fireEvent.keyDown(field, { key: 'Escape' });
    expect(closeInner).toHaveBeenCalledTimes(1);
    expect(closeOuter).not.toHaveBeenCalled();

    fireEvent.keyDown(field, { key: 'Tab' });
    const innerDialog = screen.getByRole('dialog', { name: 'Inner synthetic editor' });
    expect(within(innerDialog).getByRole('button', { name: 'Закрыть диалог' })).toHaveFocus();
  });

  it('returns focus to the original trigger after multiple edits and close', () => {
    const trigger = focusTrigger();
    const { unmount } = render(<ControlledEditor />);
    finishInitialFocus();
    const field = screen.getByRole('textbox', { name: 'Synthetic field' });
    field.focus();
    fireEvent.change(field, { target: { value: 'DEV-DEMO' } });
    fireEvent.change(field, { target: { value: 'DEV-DEMO123' } });
    finishInitialFocus();

    unmount();

    expect(trigger).toHaveFocus();
    expect(document.body.style.overflow).toBe('');
  });

  it('does not replace an already focused child with the delayed header focus', () => {
    focusTrigger();
    render(
      <ModernDialog isOpen title="Synthetic editor">
        <input aria-label="Synthetic field" autoFocus />
      </ModernDialog>,
    );
    const field = screen.getByRole('textbox', { name: 'Synthetic field' });
    expect(field).toHaveFocus();

    finishInitialFocus();

    expect(field).toHaveFocus();
  });
});
