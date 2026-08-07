import React, { forwardRef, memo } from 'react';
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
 *
 * The icon prop accepts `React.ElementType | ReactNode`. The test suite below
 * covers ALL variants the type signature allows, to ensure the icon-type
 * check is robust against every legal input:
 *   - function component
 *   - forwardRef component (custom)
 *   - memo component
 *   - forwardRef component (lucide-react — the production regression case)
 *   - ReactElement (<Package />) — pre-rendered element
 *   - string content (emoji)
 *   - string content (text — production callers use icon="calendar")
 *   - number
 *   - null
 *   - undefined
 */
describe('MacOSEmptyState — icon-type coverage (PR-8B)', () => {
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

  it('renders without error when icon is a custom forwardRef component', () => {
    const CustomForwardRef = forwardRef<HTMLSpanElement>(function CustomForwardRef() {
      return <svg data-testid="fwd-icon" />;
    });
    const { container } = render(<MacOSEmptyState icon={CustomForwardRef} title="Empty" />);
    expect(container.querySelector('svg[data-testid="fwd-icon"]')).not.toBeNull();
  });

  it('renders without error when icon is a memo component', () => {
    const CustomMemo = memo(function CustomMemo() {
      return <svg data-testid="memo-icon" />;
    });
    const { container } = render(<MacOSEmptyState icon={CustomMemo} title="Empty" />);
    expect(container.querySelector('svg[data-testid="memo-icon"]')).not.toBeNull();
  });

  it('renders without error when icon is a pre-rendered ReactElement', () => {
    const { container } = render(<MacOSEmptyState icon={<Package />} title="Empty" />);
    // ReactElement should be rendered as a child (not as <Icon />).
    // It renders into the <span>{Icon}</span> branch — the SVG still appears.
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('renders string icon as text content (backward compat — emoji)', () => {
    render(<MacOSEmptyState icon="📦" title="Empty" />);
    expect(screen.getByText('📦')).toBeInTheDocument();
  });

  it('renders string icon as text content (backward compat — text)', () => {
    // Production callers pass icon="calendar" (DermatologistPanelUnified.tsx:1743).
    render(<MacOSEmptyState icon="calendar" title="Empty" />);
    expect(screen.getByText('calendar')).toBeInTheDocument();
  });

  it('renders number icon as text content', () => {
    render(<MacOSEmptyState icon={42} title="Empty" />);
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders without error when icon is null', () => {
    render(<MacOSEmptyState icon={null} title="Empty" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Empty')).toBeInTheDocument();
  });

  it('renders without error when icon is omitted (undefined)', () => {
    render(<MacOSEmptyState title="Empty" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Empty')).toBeInTheDocument();
  });
});

