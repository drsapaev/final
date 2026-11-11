/**
 * RETRO-3994-02 (post-merge review 4000) — document-wide redo must work on
 * REAL Latin/Russian layouts.
 *
 * Red-first: on pre-fix source the redo branch matched
 * `(e.key === 'z' || e.key === 'я') && e.shiftKey` — but real browsers
 * report the SHIFTED key ('Z'/'Я') when Shift is held, so Ctrl+Shift+Z
 * never matched outside jsdom; only Ctrl+Y worked. The PR's own test
 * dispatched lowercase `{key:'z'…}` — semantics real browsers don't
 * produce.
 *
 * Post-fix contract: redo detection is case-insensitive over z/Z/я/Я:
 *  - Ctrl+Shift+Z ('Z', real Latin layout) fires document-wide redo;
 *  - Ctrl+Shift+Я ('Я', real Russian layout) fires it too;
 *  - inside editable controls the shifted keys stay native (no
 *    interception, no preventDefault — EMRKEY-FE-001 intact);
 *  - lowercase dispatches keep working (jsdom legacy + robustness);
 *  - Ctrl+Y redo and Ctrl+Z undo are unaffected by the refactor.
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
        <div data-testid="emr-non-editable" tabIndex={-1}>non-editable EMR area</div>
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

describe('RETRO-3994-02: document-wide redo works with real shifted keys', () => {
  it('Ctrl+Shift+Z (real Latin layout reports "Z") fires document-wide redo', () => {
    const { onRedo } = setup({});
    const ev = press(screen.getByTestId('emr-non-editable'), {
      key: 'Z', ctrlKey: true, shiftKey: true,
    });
    expect(onRedo).toHaveBeenCalledTimes(1);
    expect(ev.defaultPrevented).toBe(true);
  });

  it('Ctrl+Shift+Я (real Russian layout reports "Я") fires document-wide redo', () => {
    const { onRedo } = setup({});
    const ev = press(screen.getByTestId('emr-non-editable'), {
      key: 'Я', ctrlKey: true, shiftKey: true,
    });
    expect(onRedo).toHaveBeenCalledTimes(1);
    expect(ev.defaultPrevented).toBe(true);
  });

  it('CONTROL: lowercase z with shift keeps firing redo (jsdom legacy)', () => {
    const { onRedo } = setup({});
    const ev = press(screen.getByTestId('emr-non-editable'), {
      key: 'z', ctrlKey: true, shiftKey: true,
    });
    expect(onRedo).toHaveBeenCalledTimes(1);
    expect(ev.defaultPrevented).toBe(true);
  });

  it('CONTROL: Ctrl+Y keeps firing redo', () => {
    const { onRedo } = setup({});
    const ev = press(screen.getByTestId('emr-non-editable'), { key: 'y', ctrlKey: true });
    expect(onRedo).toHaveBeenCalledTimes(1);
    expect(ev.defaultPrevented).toBe(true);
  });

  it('Ctrl+Shift+Z inside an EMR textarea stays native (shifted key, no interception)', () => {
    const { onRedo } = setup({});
    const ev = press(screen.getByTestId('emr-textarea'), {
      key: 'Z', ctrlKey: true, shiftKey: true,
    });
    expect(onRedo).not.toHaveBeenCalled();
    expect(ev.defaultPrevented).toBe(false);
  });

  it('CONTROL: undo is unaffected — Ctrl+Z ("z") fires document-wide undo', () => {
    const { onUndo } = setup({});
    const ev = press(screen.getByTestId('emr-non-editable'), { key: 'z', ctrlKey: true });
    expect(onUndo).toHaveBeenCalledTimes(1);
    expect(ev.defaultPrevented).toBe(true);
  });

  it('CONTROL: shifted Z without Ctrl is ignored everywhere', () => {
    const { onUndo, onRedo } = setup({});
    const ev = press(screen.getByTestId('emr-non-editable'), { key: 'Z', shiftKey: true });
    expect(onUndo).not.toHaveBeenCalled();
    expect(onRedo).not.toHaveBeenCalled();
    expect(ev.defaultPrevented).toBe(false);
  });
});
