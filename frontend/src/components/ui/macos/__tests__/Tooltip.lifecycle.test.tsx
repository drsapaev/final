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
});
