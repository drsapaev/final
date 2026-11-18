import React, { useState } from 'react';
import { createPortal } from 'react-dom';
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

  it('keeps focus and Escape in a separate modal opened above the dialog', () => {
    focusTrigger();
    const closeEditor = vi.fn();
    const editor = (version: number) => (
      <>
        <ModernDialog
          isOpen
          onClose={closeEditor}
          ariaLabel="Synthetic editor"
          customHeader={<button type="button">Synthetic header {version}</button>}
        >
          <input aria-label="Synthetic field" />
        </ModernDialog>
        {createPortal(
          <div role="dialog" aria-modal="true" aria-label="Synthetic confirmation">
            <button type="button">Cancel confirmation</button>
          </div>,
          document.body,
        )}
      </>
    );
    const { rerender } = render(editor(1));
    finishInitialFocus();
    const confirmationButton = screen.getByRole('button', { name: 'Cancel confirmation' });
    confirmationButton.focus();

    rerender(editor(2));
    finishInitialFocus();
    expect(confirmationButton).toHaveFocus();
    fireEvent.keyDown(confirmationButton, { key: 'Escape' });
    expect(closeEditor).not.toHaveBeenCalled();
  });

  it('moves initial focus into a dialog opened from a separate modal', () => {
    render(
      <div role="dialog" aria-modal="true" aria-label="Existing modal">
        <button type="button">Open synthetic editor</button>
      </div>,
    );
    const trigger = screen.getByRole('button', { name: 'Open synthetic editor' });
    trigger.focus();

    const { unmount } = render(
      <ModernDialog isOpen ariaLabel="Synthetic editor">
        <input aria-label="Synthetic field" />
      </ModernDialog>,
    );
    finishInitialFocus();
    expect(screen.getByRole('dialog', { name: 'Synthetic editor' }))
      .toContainElement(document.activeElement as HTMLElement);

    unmount();
    expect(trigger).toHaveFocus();
  });

  it('does not take initial focus from another modal opened before the timer', () => {
    focusTrigger();
    render(
      <>
        <ModernDialog isOpen ariaLabel="Synthetic editor">
          <input aria-label="Synthetic field" />
        </ModernDialog>
        {createPortal(
          <div role="dialog" aria-modal="true" aria-label="Synthetic confirmation">
            <button type="button">Cancel confirmation</button>
          </div>,
          document.body,
        )}
      </>,
    );
    const confirmationButton = screen.getByRole('button', { name: 'Cancel confirmation' });
    confirmationButton.focus();

    finishInitialFocus();
    expect(confirmationButton).toHaveFocus();
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

  it('returns focus to the trigger after closing a dialog with an auto-focused field', () => {
    const trigger = focusTrigger();
    const { unmount } = render(
      <ModernDialog isOpen title="Synthetic editor">
        <input aria-label="Synthetic field" autoFocus />
      </ModernDialog>,
    );
    expect(screen.getByRole('textbox', { name: 'Synthetic field' })).toHaveFocus();

    unmount();

    expect(trigger).toHaveFocus();
  });

  it('remembers the new trigger when an auto-focused dialog is reopened', () => {
    const firstTrigger = focusTrigger();
    const editor = (isOpen: boolean) => (
      <ModernDialog isOpen={isOpen} title="Synthetic editor">
        <input aria-label="Synthetic field" autoFocus />
      </ModernDialog>
    );
    const { rerender } = render(editor(true));
    expect(screen.getByRole('textbox', { name: 'Synthetic field' })).toHaveFocus();

    rerender(editor(false));
    expect(firstTrigger).toHaveFocus();

    const secondTrigger = focusTrigger();
    rerender(editor(true));
    expect(screen.getByRole('textbox', { name: 'Synthetic field' })).toHaveFocus();
    rerender(editor(false));
    expect(secondTrigger).toHaveFocus();
  });

  it('initializes focus again when a dialog without autoFocus is reopened', () => {
    const firstTrigger = focusTrigger();
    const editor = (isOpen: boolean) => (
      <ModernDialog isOpen={isOpen} title="Synthetic editor">
        <input aria-label="Synthetic field" />
      </ModernDialog>
    );
    const { rerender } = render(editor(true));
    finishInitialFocus();
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement);

    rerender(editor(false));
    expect(firstTrigger).toHaveFocus();
    const secondTrigger = focusTrigger();
    rerender(editor(true));
    finishInitialFocus();
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement);

    rerender(editor(false));
    expect(secondTrigger).toHaveFocus();
  });

  it('preserves initial autoFocus and returns to the trigger in StrictMode', () => {
    const trigger = focusTrigger();
    const { unmount } = render(
      <React.StrictMode>
        <ModernDialog isOpen title="Synthetic editor">
          <input aria-label="Synthetic field" autoFocus />
        </ModernDialog>
      </React.StrictMode>,
    );
    const field = screen.getByRole('textbox', { name: 'Synthetic field' });
    expect(field).toHaveFocus();
    finishInitialFocus();
    expect(field).toHaveFocus();

    unmount();
    expect(trigger).toHaveFocus();
  });

  it('returns focus to the outer dialog after closing an auto-focused inner dialog', () => {
    focusTrigger();
    const dialogs = (innerOpen: boolean) => (
      <ModernDialog isOpen title="Outer synthetic editor">
        <button type="button">Open inner editor</button>
        <ModernDialog isOpen={innerOpen} title="Inner synthetic editor">
          <input aria-label="Inner synthetic field" autoFocus />
        </ModernDialog>
      </ModernDialog>
    );
    const { rerender } = render(dialogs(false));
    finishInitialFocus();
    const innerTrigger = screen.getByRole('button', { name: 'Open inner editor' });
    innerTrigger.focus();

    rerender(dialogs(true));
    expect(screen.getByRole('textbox', { name: 'Inner synthetic field' })).toHaveFocus();
    rerender(dialogs(false));
    expect(innerTrigger).toHaveFocus();
  });
});
