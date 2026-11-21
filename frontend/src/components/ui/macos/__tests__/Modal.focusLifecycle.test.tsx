import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import Modal from '../Modal';

vi.mock('@/contexts/ThemeContext', () => ({ useTheme: () => ({}) }));
vi.mock('@/i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

let frames: Map<number, FrameRequestCallback>;
let nextFrame: number;
let trigger: HTMLButtonElement;

const runFrame = (id: number) => {
  const callback = frames.get(id);
  frames.delete(id);
  if (callback) act(() => callback(0));
};

beforeEach(() => {
  frames = new Map();
  nextFrame = 0;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    const id = ++nextFrame;
    frames.set(id, callback);
    return id;
  });
  vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id));
  trigger = document.createElement('button');
  trigger.textContent = 'Open synthetic dialog';
  document.body.appendChild(trigger);
  trigger.focus();
});

afterEach(() => {
  cleanup();
  trigger.remove();
  vi.unstubAllGlobals();
});

describe('macOS Modal focus lifecycle', () => {
  it('keeps focus in an open modal when callbacks change and uses the latest Escape handler', () => {
    const firstClose = vi.fn();
    const latestClose = vi.fn();
    const modal = (onClose: () => void, closeOnEscape = true) => (
      <Modal isOpen title="Synthetic confirmation" onClose={onClose} closeOnEscape={closeOnEscape}>
        <input aria-label="Synthetic confirmation field" />
      </Modal>
    );
    const { rerender, unmount } = render(modal(firstClose));
    runFrame(1);
    const field = screen.getByRole('textbox', { name: 'Synthetic confirmation field' });
    field.focus();

    rerender(modal(latestClose, false));
    expect(field).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(firstClose).not.toHaveBeenCalled();
    expect(latestClose).not.toHaveBeenCalled();

    rerender(modal(latestClose));
    expect(field).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(latestClose).toHaveBeenCalledTimes(1);
    expect(firstClose).not.toHaveBeenCalled();

    unmount();
    expect(trigger).toHaveFocus();
  });

  it('does not let an animation frame from a closed modal move focus after reopening', () => {
    const modal = (isOpen: boolean) => (
      <Modal isOpen={isOpen} title="Synthetic confirmation" onClose={() => {}}>
        <input aria-label="Synthetic confirmation field" />
      </Modal>
    );
    const { rerender } = render(modal(true));
    rerender(modal(false));
    rerender(modal(true));
    const field = screen.getByRole('textbox', { name: 'Synthetic confirmation field' });
    field.focus();

    runFrame(1);
    expect(field).toHaveFocus();
  });
});
