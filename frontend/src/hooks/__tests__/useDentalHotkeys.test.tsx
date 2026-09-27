import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useDentalHotkeys } from '../useDentalHotkeys';

describe('useDentalHotkeys', () => {
  it('lets an open modal consume Escape without clearing the selected patient', () => {
    const clearSelection = vi.fn();
    const { unmount } = renderHook(() => useDentalHotkeys({ clearSelection }));
    const dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    const control = document.createElement('button');
    dialog.append(control);
    document.body.append(dialog);

    act(() => {
      control.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });

    expect(clearSelection).not.toHaveBeenCalled();
    unmount();
    dialog.remove();
  });

  it('clears the patient with Escape when no modal is open', () => {
    const clearSelection = vi.fn();
    const { unmount } = renderHook(() => useDentalHotkeys({ clearSelection }));

    act(() => {
      document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });

    expect(clearSelection).toHaveBeenCalledTimes(1);
    unmount();
  });
});
