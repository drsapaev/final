/**
 * DataCard canonical contract tests.
 *
 * PR-UI-11-1 (dashboard data-first).
 *
 * ## Test organization
 *
 * The 10 tests split into four buckets:
 *
 *   DC-1..3 — header rendering (header present/absent, title block, action slot)
 *   DC-4..6 — body state branches (loading skeleton default/custom, error + retry,
 *             empty state)
 *   DC-7..9 — variants / density / aria pass-through (variant → Card variant,
 *             density → Card padding, aria-busy toggled on loading)
 *   DC-10   — body className merge (custom bodyClassName appended without
 *             clobbering the data-card__body base class)
 *
 * The component under test is `frontend/src/components/ui/DataCard.tsx` —
 * a thin wrapper over the canonical `Card` + `AppEmpty` + `Skeleton`
 * primitives. These tests lock the wrapper contract; the underlying Card /
 * Skeleton / AppEmpty have their own dedicated test files.
 */

import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ReactElement } from 'react';

import { ThemeProvider } from '@/contexts/ThemeContext';

import DataCard from '../DataCard';

const renderWithTheme = (ui: ReactElement) => render(<ThemeProvider>{ui}</ThemeProvider>);

describe('DataCard — header rendering (DC-1..3)', () => {
  it('DC-1: renders header when title is provided', () => {
    renderWithTheme(<DataCard title="Today’s schedule">body</DataCard>);
    expect(screen.getByText('Today’s schedule')).toBeInTheDocument();
    expect(screen.getByText('body')).toBeInTheDocument();
  });

  it('DC-2: omits the header entirely when no header props are passed', () => {
    const { container } = renderWithTheme(<DataCard>body</DataCard>);
    // The header element is identified by the .data-card__header class.
    expect(container.querySelector('.data-card__header')).toBeNull();
    expect(container.querySelector('.data-card__body')).not.toBeNull();
  });

  it('DC-3: renders icon, title, description, badge, and action in the header', () => {
    renderWithTheme(
      <DataCard
        title="Queue summary"
        description="Aggregate across departments"
        icon={<span data-testid="dc-icon">⏱</span>}
        badge={<span data-testid="dc-badge">3</span>}
        action={<button type="button" data-testid="dc-action">Refresh</button>}
      >
        body
      </DataCard>
    );
    expect(screen.getByTestId('dc-icon')).toBeInTheDocument();
    expect(screen.getByText('Queue summary')).toBeInTheDocument();
    expect(screen.getByText('Aggregate across departments')).toBeInTheDocument();
    expect(screen.getByTestId('dc-badge')).toBeInTheDocument();
    expect(screen.getByTestId('dc-action')).toBeInTheDocument();
  });
});

describe('DataCard — body state branches (DC-4..6)', () => {
  it('DC-4: renders default skeleton when loading and no loadingSkeleton is supplied', () => {
    const { container } = renderWithTheme(<DataCard title="t" loading>body</DataCard>);
    // The Skeleton primitive injects animated placeholder elements; we
    // assert that the body content is NOT visible (loading branch wins)
    // and that the wrapper exposes the aria-busy status.
    expect(screen.queryByText('body')).toBeNull();
    const section = container.querySelector('[aria-busy="true"]');
    expect(section).not.toBeNull();
  });

  it('DC-4b: renders custom loadingSkeleton when supplied', () => {
    renderWithTheme(
      <DataCard title="t" loading loadingSkeleton={<div data-testid="custom-skeleton">…</div>}>
        body
      </DataCard>
    );
    expect(screen.getByTestId('custom-skeleton')).toBeInTheDocument();
    expect(screen.queryByText('body')).toBeNull();
  });

  it('DC-5: renders error state with retry button when error + onRetry are supplied', () => {
    const onRetry = vi.fn();
    renderWithTheme(
      <DataCard title="t" error="Failed to load" onRetry={onRetry} retryLabel="Retry">
        body
      </DataCard>
    );
    expect(screen.queryByText('body')).toBeNull();
    expect(screen.getByText('Failed to load')).toBeInTheDocument();
    const retryButton = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryButton);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('DC-5b: error state without onRetry does not render a retry button', () => {
    renderWithTheme(<DataCard title="t" error="Failed">body</DataCard>);
    expect(screen.queryByText('body')).toBeNull();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('DC-6: renders empty state when empty is supplied and not loading/error', () => {
    renderWithTheme(<DataCard title="t" empty="No data">body</DataCard>);
    expect(screen.queryByText('body')).toBeNull();
    expect(screen.getByText('No data')).toBeInTheDocument();
  });
});

describe('DataCard — variant / density / aria pass-through (DC-7..9)', () => {
  it('DC-7: variant="outlined" surfaces on the underlying Card', () => {
    const { container } = renderWithTheme(<DataCard title="t" variant="outlined">body</DataCard>);
    // Card applies variant inline via backgroundColor/border.
    const card = container.querySelector('.data-card');
    expect(card).not.toBeNull();
    // Outlined sets backgroundColor transparent + 2px border.
    expect(card?.getAttribute('style')).toContain('transparent');
  });

  it('DC-8: density="compact" surfaces on the underlying Card (padding small)', () => {
    const { container } = renderWithTheme(<DataCard title="t" density="compact">body</DataCard>);
    const card = container.querySelector('.data-card');
    expect(card).not.toBeNull();
    expect(card?.getAttribute('style')).toContain('padding: 12px');
  });

  it('DC-9: aria-label + aria-busy are forwarded to the outer Card', () => {
    const { container } = renderWithTheme(
      <DataCard title="t" ariaLabel="Queue panel" loading>body</DataCard>
    );
    const card = container.querySelector('.data-card');
    expect(card?.getAttribute('aria-label')).toBe('Queue panel');
    expect(card?.getAttribute('aria-busy')).toBe('true');

    // When loading flips off, aria-busy disappears. Use a fresh tree
    // instead of rerender — `rerender` from `renderWithTheme` would
    // replace the ThemeProvider root, dropping the `useTheme()` context.
    const { container: container2 } = renderWithTheme(
      <DataCard title="t" ariaLabel="Queue panel">body</DataCard>
    );
    expect(container2.querySelector('.data-card')?.getAttribute('aria-busy')).toBeNull();
  });
});

describe('DataCard — body className merge (DC-10)', () => {
  it('DC-10: bodyClassName is appended to the data-card__body base class', () => {
    const { container } = renderWithTheme(
      <DataCard title="t" bodyClassName="custom-body">body</DataCard>
    );
    const bodyEl = container.querySelector('.data-card__body');
    expect(bodyEl?.className).toContain('data-card__body');
    expect(bodyEl?.className).toContain('custom-body');
  });
});
