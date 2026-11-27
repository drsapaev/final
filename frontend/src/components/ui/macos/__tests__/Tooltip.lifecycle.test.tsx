import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import Tooltip from '../Tooltip';

describe('Tooltip hover lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 0;
    });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('hides after pointer leave and can reopen on a later hover', () => {
    render(
      <ThemeProvider>
        <Tooltip content="Help" delay={50}>
          <button type="button">Trigger</button>
        </Tooltip>
      </ThemeProvider>,
    );

    const button = screen.getByRole('button', { name: 'Trigger' });
    const trigger = button.closest('.mac-tooltip-trigger');
    expect(trigger).not.toBeNull();

    fireEvent.pointerEnter(trigger!);
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    expect(screen.getByRole('tooltip')).toHaveStyle({ opacity: '1' });

    fireEvent.pointerLeave(trigger!);
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    fireEvent.pointerEnter(trigger!);
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
  });

  it('cancels the pending hide when the pointer re-enters during the exit window', () => {
    render(
      <ThemeProvider>
        <Tooltip content="Help" delay={50}>
          <button type="button">Trigger</button>
        </Tooltip>
      </ThemeProvider>,
    );

    const button = screen.getByRole('button', { name: 'Trigger' });
    const trigger = button.closest('.mac-tooltip-trigger');
    expect(trigger).not.toBeNull();

    fireEvent.pointerEnter(trigger!);
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(screen.getByRole('tooltip')).toHaveStyle({ opacity: '1' });

    fireEvent.pointerLeave(trigger!);
    expect(screen.getByRole('tooltip')).toHaveStyle({ opacity: '0' });

    act(() => {
      vi.advanceTimersByTime(100);
    });
    fireEvent.pointerEnter(trigger!);

    expect(screen.getByRole('tooltip')).toHaveStyle({ opacity: '1' });

    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    expect(screen.getByRole('tooltip')).toHaveStyle({ opacity: '1' });
  });
  it('shows an opt-in decorative hint on focus, dismisses on Escape without blur, and reopens', () => {
    render(
      <ThemeProvider>
        <Tooltip content="Refresh" delay={50} decorativeHint>
          <button type="button" aria-label="Refresh">↻</button>
        </Tooltip>
        <button type="button">Next</button>
      </ThemeProvider>,
    );
    const button = screen.getByRole('button', { name: 'Refresh' });
    act(() => button.focus());
    act(() => vi.advanceTimersByTime(50));
    expect(screen.getByText('Refresh').closest('.mac-tooltip')).toHaveAttribute('aria-hidden', 'true');
    expect(button).not.toHaveAccessibleDescription();

    fireEvent.keyDown(button, { key: 'Escape' });
    expect(screen.queryByText('Refresh')).not.toBeInTheDocument();
    expect(button).toHaveFocus();

    act(() => screen.getByRole('button', { name: 'Next' }).focus());
    act(() => button.focus());
    act(() => vi.advanceTimersByTime(50));
    expect(screen.getByText('Refresh')).toBeInTheDocument();

    act(() => screen.getByRole('button', { name: 'Next' }).focus());
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByText('Refresh')).not.toBeInTheDocument();
  });

  it('keeps the opt-in hint open over the bubble and dismisses hover without button focus', () => {
    const onAncestorClick = vi.fn();
    render(
      <ThemeProvider>
        <div onClick={onAncestorClick} role="presentation">
          <Tooltip content="Preview hint" delay={50} decorativeHint>
            <button type="button" aria-label="Preview file">⌕</button>
          </Tooltip>
        </div>
      </ThemeProvider>,
    );
    const trigger = screen.getByRole('button', { name: 'Preview file' }).closest('.mac-tooltip-trigger')!;
    fireEvent.pointerEnter(trigger);
    act(() => vi.advanceTimersByTime(50));
    const bubble = screen.getByText('Preview hint').closest('.mac-tooltip')!;
    fireEvent.pointerLeave(trigger);
    fireEvent.pointerEnter(bubble);
    act(() => vi.advanceTimersByTime(200));
    expect(bubble).toHaveStyle({ opacity: '1' });
    fireEvent.click(bubble);
    expect(onAncestorClick).not.toHaveBeenCalled();
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(screen.queryByText('Preview hint')).not.toBeInTheDocument();
  });

});
