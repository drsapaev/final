/**
 * DERMAHOTKEY-FE-001 (audit 3892, post-merge group 9) — fail-first
 * regression for the derma Escape hotkey, first half (modal gate):
 *
 * An Escape keystroke while a modal dialog owns the screen must not clear
 * the active patient/visit selection underneath it. The dental hook
 * (useDentalHotkeys) already implements this gate; the derma hook must
 * match it.
 *
 * Red-first: on the pre-fix source the dialog case fails (the selection is
 * cleared); the no-dialog and input-focus controls pass on both.
 */
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useDermaHotkeys } from '../useDermaHotkeys';

function pressEscape(target: HTMLElement) {
  act(() => {
    target.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  });
}

describe('useDermaHotkeys — Escape modal gate (DERMAHOTKEY-FE-001)', () => {
  it('lets an open modal consume Escape without clearing the selected visit (pre-fix: cleared)', () => {
    const clearSelection = vi.fn();
    const { unmount } = renderHook(() => useDermaHotkeys({ clearSelection }));

    const dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    const control = document.createElement('button');
    dialog.append(control);
    document.body.append(dialog);

    pressEscape(control);

    expect(clearSelection).not.toHaveBeenCalled();
    unmount();
    dialog.remove();
  });

  it('positive control: clears the selection with Escape when no modal is open', () => {
    const clearSelection = vi.fn();
    const { unmount } = renderHook(() => useDermaHotkeys({ clearSelection }));

    pressEscape(document.body);

    expect(clearSelection).toHaveBeenCalledTimes(1);
    unmount();
  });

  it('positive control: Escape from a focused input never clears the selection', () => {
    const clearSelection = vi.fn();
    const { unmount } = renderHook(() => useDermaHotkeys({ clearSelection }));

    const input = document.createElement('input');
    document.body.append(input);
    pressEscape(input);

    expect(clearSelection).not.toHaveBeenCalled();
    unmount();
    input.remove();
  });
});
