
/**
 * EMRKEY-FE-001 (audit 3886, round 30).
 *
 * Red-first contract suite for the EMR document-wide keyboard shortcuts.
 * On pre-fix source:
 *  - Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y pressed while the focus is inside an
 *    editable control (even inside `.emr-section`) were intercepted with
 *    `preventDefault()` and dispatched the REDUCER-wide UNDO/REDO — the
 *    whole EMR state rewound to an earlier snapshot instead of the browser's
 *    native per-field text undo, silently rolling back unrelated clinical
 *    fields;
 *  - `preventDefault()` was called even when `canUndo`/`canRedo` was false,
 *    so an unavailable action still swallowed the native event.
 *
 * Post-fix contract:
 *  - inside ANY editable control (INPUT/TEXTAREA/SELECT/contenteditable)
 *    undo/redo keys are never intercepted — native text editing history
 *    stays with the browser;
 *  - outside editable controls the document-wide reducer undo/redo keeps
 *    working (and only then prevents the default);
 *  - an unavailable undo/redo action does not preventDefault;
 *  - Ctrl+S (autosave intent) and Ctrl+Enter (sign) keep their EMR
 *    in-input behavior unchanged.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useEMRKeyboard } from '../useEMRKeyboard';

type Handlers = {
  onSave?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  onSign?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  canSave?: boolean;
  canSign?: boolean;
  enabled?: boolean;
};

function Harness({ handlers }: { handlers: Handlers }) {
  useEMRKeyboard({
    onSave: handlers.onSave,
    onUndo: handlers.onUndo,
    onRedo: handlers.onRedo,
    onSign: handlers.onSign,
    canUndo: handlers.canUndo ?? true,
    canRedo: handlers.canRedo ?? true,
    canSave: handlers.canSave ?? true,
    canSign: handlers.canSign ?? false,
    enabled: handlers.enabled ?? true,
  });
  return (
    <>
      <div className="emr-section" data-testid="emr-root">
        <textarea data-testid="emr-textarea" aria-label="Диагноз" />
        <input data-testid="emr-input" aria-label="Жалобы" />
        <div data-testid="emr-non-editable" tabIndex={-1}>non-editable EMR area</div>
      </div>
      <div data-testid="outside-root">
        <textarea data-testid="outside-textarea" aria-label="Вне ЭМК" />
      </div>
    </>
  );
}

/** Dispatches a bubbling, cancelable keydown and returns it for inspection. */
function press(target: HTMLElement, init: KeyboardEventInit): KeyboardEvent {
  const event = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init });
  target.dispatchEvent(event);
  return event;
}

function setup(handlers: Handlers) {
  const onSave = vi.fn();
  const onUndo = vi.fn();
  const onRedo = vi.fn();
  const onSign = vi.fn();
  render(<Harness handlers={{ ...handlers, onSave, onUndo, onRedo, onSign }} />);
  return { onSave, onUndo, onRedo, onSign };
}

describe('EMRKEY-FE-001 — native text undo is never hijacked by the EMR reducer history', () => {
  it('Ctrl+Z inside an EMR textarea does NOT dispatch reducer undo and does NOT preventDefault', () => {
    const { onUndo } = setup({});
    const ev = press(screen.getByTestId('emr-textarea'), { key: 'z', ctrlKey: true });
    expect(onUndo).not.toHaveBeenCalled();
    expect(ev.defaultPrevented).toBe(false);
  });

  it('Ctrl+Shift+Z and Ctrl+Y inside an EMR textarea do NOT dispatch reducer redo', () => {
    const { onRedo } = setup({});
    const evRedoShift = press(screen.getByTestId('emr-textarea'), { key: 'z', ctrlKey: true, shiftKey: true });
    expect(onRedo).not.toHaveBeenCalled();
    expect(evRedoShift.defaultPrevented).toBe(false);

    const evRedoY = press(screen.getByTestId('emr-input'), { key: 'y', ctrlKey: true });
    expect(onRedo).not.toHaveBeenCalled();
    expect(evRedoY.defaultPrevented).toBe(false);
  });

  it('Russian-layout undo/redo keys (я/н) inside text inputs stay native too', () => {
    const { onUndo, onRedo } = setup({});
    const evUndo = press(screen.getByTestId('emr-textarea'), { key: 'я', ctrlKey: true });
    expect(onUndo).not.toHaveBeenCalled();
    expect(evUndo.defaultPrevented).toBe(false);

    const evRedo = press(screen.getByTestId('emr-textarea'), { key: 'н', ctrlKey: true });
    expect(onRedo).not.toHaveBeenCalled();
    expect(evRedo.defaultPrevented).toBe(false);
  });

  it('document-wide reducer undo/redo still works OUTSIDE editable controls', () => {
    const { onUndo, onRedo } = setup({});
    const evUndo = press(screen.getByTestId('emr-non-editable'), { key: 'z', ctrlKey: true });
    expect(onUndo).toHaveBeenCalledTimes(1);
    expect(evUndo.defaultPrevented).toBe(true);

    const evRedo = press(screen.getByTestId('emr-non-editable'), { key: 'z', ctrlKey: true, shiftKey: true });
    expect(onRedo).toHaveBeenCalledTimes(1);
    expect(evRedo.defaultPrevented).toBe(true);
  });

  it('unavailable undo/redo outside editables does not preventDefault the event', () => {
    const { onUndo, onRedo } = setup({ canUndo: false, canRedo: false });
    const evUndo = press(screen.getByTestId('emr-non-editable'), { key: 'z', ctrlKey: true });
    expect(onUndo).not.toHaveBeenCalled();
    expect(evUndo.defaultPrevented).toBe(false);

    const evRedo = press(screen.getByTestId('emr-non-editable'), { key: 'y', ctrlKey: true });
    expect(onRedo).not.toHaveBeenCalled();
    expect(evRedo.defaultPrevented).toBe(false);
  });

  it('unavailable undo inside a NON-EMR input stays native (QW-2 behavior intact)', () => {
    const { onUndo } = setup({ canUndo: false });
    const ev = press(screen.getByTestId('outside-textarea'), { key: 'z', ctrlKey: true });
    expect(onUndo).not.toHaveBeenCalled();
    expect(ev.defaultPrevented).toBe(false);
  });

  it('CONTROL: Ctrl+S inside an EMR textarea still triggers the EMR save intent', () => {
    const { onSave } = setup({});
    const ev = press(screen.getByTestId('emr-textarea'), { key: 's', ctrlKey: true });
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(ev.defaultPrevented).toBe(true);
  });

  it('CONTROL: Ctrl+Enter with canSign inside an EMR textarea still triggers sign', () => {
    const { onSign } = setup({ canSign: true });
    const ev = press(screen.getByTestId('emr-textarea'), { key: 'Enter', ctrlKey: true });
    expect(onSign).toHaveBeenCalledTimes(1);
    expect(ev.defaultPrevented).toBe(true);
  });

  it('CONTROL: Ctrl+S in a non-EMR input is not intercepted (QW-2 behavior intact)', () => {
    const { onSave } = setup({});
    const ev = press(screen.getByTestId('outside-textarea'), { key: 's', ctrlKey: true });
    expect(onSave).not.toHaveBeenCalled();
    expect(ev.defaultPrevented).toBe(false);
  });
});
