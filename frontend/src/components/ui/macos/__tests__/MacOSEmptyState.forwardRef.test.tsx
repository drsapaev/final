import React from 'react';
import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Package } from 'lucide-react';

import MacOSEmptyState from '../MacOSEmptyState';

/**
 * Regression test for PR-8B: MacOSEmptyState must handle forwardRef/memo
 * icon components (e.g. lucide-react icons).
 *
 * Previously, the icon-type check used `typeof Icon === 'function'`, which
 * missed forwardRef objects ({$$typeof, render}). Those fell through to the
 * `<span>{Icon}</span>` branch, and React threw
 * "Objects are not valid as a React child (found: object with keys {$$typeof, render})"
 * — breaking every production caller that passed a lucide-react icon
 * (ServiceCatalog, MedicalEquipmentManager, BranchManagement, BackupManagement).
 *
 * This test guards against regression by rendering with a real lucide-react
 * icon and asserting the component mounts without error and the icon SVG
 * is rendered into the DOM.
 */
describe('MacOSEmptyState — forwardRef icon regression (PR-8B)', () => {
  it('renders without error when icon is a forwardRef component (lucide-react)', () => {
    const { container } = render(
      <MacOSEmptyState
        icon={Package}
        title="Нет услуг"
        description="Услуги пока не добавлены"
      />
    );

    // role="status" must be present (a11y contract).
    expect(screen.getByRole('status')).toBeInTheDocument();

    // The lucide-react Package icon renders as an <svg> element.
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('aria-hidden')).toBe('true');
    expect(svg?.getAttribute('focusable')).toBe('false');
  });

  it('renders the title text', () => {
    render(<MacOSEmptyState icon={Package} title="Пусто" />);
    expect(screen.getByText('Пусто')).toBeInTheDocument();
  });

  it('renders without error when icon is a plain function component', () => {
    function CustomIcon() {
      return <svg data-testid="custom-icon" />;
    }
    const { container } = render(<MacOSEmptyState icon={CustomIcon} title="Empty" />);
    expect(container.querySelector('svg[data-testid="custom-icon"]')).not.toBeNull();
  });

  it('renders string icon as text content (backward compat)', () => {
    render(<MacOSEmptyState icon="📦" title="Empty" />);
    expect(screen.getByText('📦')).toBeInTheDocument();
  });

  it('renders without error when icon is omitted', () => {
    render(<MacOSEmptyState title="Empty" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Empty')).toBeInTheDocument();
  });
});
