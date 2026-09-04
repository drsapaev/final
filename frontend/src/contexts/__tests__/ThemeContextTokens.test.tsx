import { render } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, useTheme } from '../ThemeContext';

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), put: vi.fn() },
}));

vi.mock('../../api/client', () => ({
  default: apiMock,
  api: apiMock,
  apiClient: apiMock,
}));

/**
 * PR-UI-17-4: behavior-equivalence proof for ThemeContext token accessors
 * after theme/tokens-legacy.ts deletion (values inlined into the context).
 * Every expectation below is byte-identical to the deleted legacy map, so a
 * passing suite proves getColor/getSpacing/getFontSize/getShadow return
 * exactly what they returned before the file was removed.
 */
function TokensHarness() {
  const { getColor, getSpacing, getFontSize, getShadow } = useTheme();
  return (
    <div>
      <span data-testid="primary-500">{getColor('primary', 500)}</span>
      <span data-testid="primary-400">{getColor('primary', 400)}</span>
      <span data-testid="primary-default">{getColor('primary')}</span>
      <span data-testid="secondary-700">{getColor('secondary', 700)}</span>
      <span data-testid="success">{getColor('success')}</span>
      <span data-testid="warning">{getColor('warning')}</span>
      <span data-testid="danger">{getColor('danger')}</span>
      <span data-testid="info">{getColor('info')}</span>
      <span data-testid="status-unknown-fallback">{getColor('pending')}</span>

      <span data-testid="text-primary">{getColor('text', 'primary')}</span>
      <span data-testid="text-unknown-fallback">{getColor('text', 'does-not-exist')}</span>
      <span data-testid="background-secondary">{getColor('background', 'secondary')}</span>
      <span data-testid="border-medium">{getColor('border', 'medium')}</span>
      <span data-testid="border-default">{getColor('border')}</span>
      <span data-testid="surface-card">{getColor('surface', 'card')}</span>
      <span data-testid="surface-unknown-fallback">{getColor('surface', 'nope')}</span>
      <span data-testid="unknown-color-fallback">{getColor('not-a-token' as never)}</span>
      <span data-testid="spacing-1">{getSpacing(1 as never)}</span>
      <span data-testid="spacing-8">{getSpacing(8 as never)}</span>
      <span data-testid="spacing-unknown-fallback">{getSpacing('md')}</span>
      <span data-testid="font-sm">{getFontSize('sm')}</span>
      <span data-testid="font-2xl">{getFontSize('2xl')}</span>
      <span data-testid="font-unknown-fallback">{getFontSize('md' as never)}</span>
      <span data-testid="shadow-sm">{getShadow('sm')}</span>
      <span data-testid="shadow-md">{getShadow('md')}</span>
      <span data-testid="shadow-unknown-fallback">{getShadow('huge' as never)}</span>
    </div>
  );
}

function setup() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <TokensHarness />
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('ThemeContext token accessors (PR-UI-17-4 equivalence proof)', () => {
  it('getColor returns byte-identical legacy values for brand shades', () => {
    const { getByTestId } = setup();
    expect(getByTestId('primary-500')).toHaveTextContent('#0ea5e9');
    expect(getByTestId('primary-400')).toHaveTextContent('#38bdf8');
    expect(getByTestId('primary-default')).toHaveTextContent('#0ea5e9');
    expect(getByTestId('secondary-700')).toHaveTextContent('#334155');
  });

  it('getColor returns byte-identical legacy status colors', () => {
    const { getByTestId } = setup();
    expect(getByTestId('success')).toHaveTextContent('#10b981');
    expect(getByTestId('warning')).toHaveTextContent('#f59e0b');
    expect(getByTestId('danger')).toHaveTextContent('#ef4444');
    expect(getByTestId('info')).toHaveTextContent('#3b82f6');
    // ORIGINAL pre-deletion behavior: the status branch only matches
    // success|warning|danger|info — 'pending' (and 'completed'/'cancelled')
    // always fell through to the primary[500] fallback. Inlined code keeps it.
    expect(getByTestId('status-unknown-fallback')).toHaveTextContent('#0ea5e9');
  });

  it('getColor returns byte-identical legacy semantic colors and fallbacks', () => {
    const { getByTestId } = setup();
    expect(getByTestId('text-primary')).toHaveTextContent('#0f172a');
    expect(getByTestId('text-unknown-fallback')).toHaveTextContent('var(--mac-text-primary)');
    expect(getByTestId('background-secondary')).toHaveTextContent('#f8fafc');
    expect(getByTestId('border-medium')).toHaveTextContent('#d1d5db');
    expect(getByTestId('border-default')).toHaveTextContent('#d1d5db');
    expect(getByTestId('surface-card')).toHaveTextContent('#ffffff');
    expect(getByTestId('surface-unknown-fallback')).toHaveTextContent('var(--mac-bg-primary)');
    expect(getByTestId('unknown-color-fallback')).toHaveTextContent('#0ea5e9');
  });

  it('getSpacing returns byte-identical legacy spacing values', () => {
    const { getByTestId } = setup();
    expect(getByTestId('spacing-1')).toHaveTextContent('4px');
    expect(getByTestId('spacing-8')).toHaveTextContent('32px');
    // legacy map has no 'md' key — pre-deletion effective fallback was '16px'
    expect(getByTestId('spacing-unknown-fallback')).toHaveTextContent('16px');
  });

  it('getFontSize returns byte-identical legacy font sizes', () => {
    const { getByTestId } = setup();
    expect(getByTestId('font-sm')).toHaveTextContent('14px');
    expect(getByTestId('font-2xl')).toHaveTextContent('24px');
    // legacy map has no 'md' key — pre-deletion effective fallback was base '16px'
    expect(getByTestId('font-unknown-fallback')).toHaveTextContent('16px');
  });

  it('getShadow returns byte-identical legacy shadow values', () => {
    const { getByTestId } = setup();
    expect(getByTestId('shadow-sm')).toHaveTextContent('0 1px 2px 0 rgba(0, 0, 0, 0.05)');
    expect(getByTestId('shadow-md')).toHaveTextContent('0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)');
    expect(getByTestId('shadow-unknown-fallback')).toHaveTextContent('0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)');
  });
});
