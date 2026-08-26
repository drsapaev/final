import React, { forwardRef, memo } from 'react';
import { createPortal } from 'react-dom';
import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Package } from 'lucide-react';

import { AppEmpty } from '../AppState';

/**
 * PR-UI-07a-8a: icon-type coverage for AppEmpty.
 *
 * Migration of the PR-8B regression guard previously carried exclusively by
 * MacOSEmptyState.forwardRef.test.tsx. Since PR-UI-07a-8a AppEmpty owns its
 * rendering (inlined from MacOSEmptyState, size="md" / variant="minimal"),
 * the icon-discrimination contract is guarded here against the public
 * primitive directly.
 *
 * AppEmpty accepts `icon?: ReactNode | ComponentType<IconWrapperProps>` and
 * routes it through normalizeIcon before discriminating:
 *
 *   - component types (function, forwardRef, memo — e.g. lucide-react icons)
 *     render as <Icon aria-hidden focusable=false style={iconStyle} />;
 *   - ReactElements (e.g. <Package />) are wrapped by normalizeIcon into a
 *     component and rendered through cloneElement with a style merge where
 *     the element's own style wins over the wrapper iconStyle
 *     (StateWrapper/AlertCircle precedent from PR-UI-07a-4);
 *   - strings, numbers, portals and arrays are plain ReactNode children and
 *     render through the <span aria-hidden>{icon}</span> branch (no
 *     iconStyle);
 *   - null/undefined render no icon at all.
 *
 * The historical crash this guard protects against: `typeof Icon ===
 * 'function'` missed forwardRef/memo objects, which fell into the span
 * branch and threw "Objects are not valid as a React child".
 */
describe('AppEmpty — icon-type coverage (PR-8B guard, migrated)', () => {
  it('renders a lucide-react forwardRef icon without error, with a11y attributes', () => {
    const { container } = render(
      <AppEmpty
        icon={Package}
        title="Нет услуг"
        description="Услуги пока не добавлены"
      />
    );

    // Outer section contract: aria-label from title, mac-app-empty class.
    const section = container.querySelector('section.mac-app-empty');
    expect(section).not.toBeNull();
    expect(section).toHaveAttribute('aria-label', 'Нет услуг');

    // Inner status contract.
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveAttribute('aria-atomic', 'true');

    // The lucide-react Package icon renders as an <svg> element with the
    // icon branch's accessibility attributes.
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('aria-hidden')).toBe('true');
    expect(svg?.getAttribute('focusable')).toBe('false');
  });

  it('applies the md iconStyle to component icons (48px, tertiary, 0.6)', () => {
    const { container } = render(<AppEmpty icon={Package} title="Empty" />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg).toHaveStyle({ width: '48px', height: '48px', opacity: '0.6' });
  });

  it('renders the title text', () => {
    render(<AppEmpty icon={Package} title="Пусто" />);
    expect(screen.getByText('Пусто')).toBeInTheDocument();
  });

  it('renders without error when icon is a plain function component', () => {
    function CustomIcon() {
      return <svg data-testid="custom-icon" />;
    }
    const { container } = render(<AppEmpty icon={CustomIcon} title="Empty" />);
    expect(container.querySelector('svg[data-testid="custom-icon"]')).not.toBeNull();
  });

  it('renders without error when icon is a custom forwardRef component', () => {
    // Typed to satisfy the public AppEmptyProps signature
    // (ComponentType<IconWrapperProps>) — the same shape lucide-react
    // forwardRef icons expose.
    const CustomForwardRef = forwardRef<HTMLSpanElement, { style?: React.CSSProperties }>(
      function CustomForwardRef() {
        return <svg data-testid="fwd-icon" />;
      }
    );
    const { container } = render(<AppEmpty icon={CustomForwardRef} title="Empty" />);
    expect(container.querySelector('svg[data-testid="fwd-icon"]')).not.toBeNull();
  });

  it('renders without error when icon is a memo component', () => {
    const CustomMemo = memo(function CustomMemo() {
      return <svg data-testid="memo-icon" />;
    });
    const { container } = render(<AppEmpty icon={CustomMemo} title="Empty" />);
    expect(container.querySelector('svg[data-testid="memo-icon"]')).not.toBeNull();
  });

  it('renders a ReactElement icon through the cloneElement merge path', () => {
    const { container } = render(<AppEmpty icon={<Package />} title="Empty" />);
    // normalizeIcon wraps the element into a component, so it renders via
    // the component branch — the SVG appears with wrapper iconStyle applied.
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('aria-hidden')).toBe('true');
    expect(svg?.getAttribute('focusable')).toBe('false');
    expect(svg).toHaveStyle({ width: '48px', height: '48px' });
  });

  it('merges styles with the element own style winning (StateWrapper precedent)', () => {
    // PR-UI-07a-4 relied on this precedence to keep AlertCircle at
    // 36px/red/opacity 1 inside AppEmpty: cloneElement merges
    // {...wrapper iconStyle, ...element's own style}.
    const { container } = render(
      <AppEmpty
        icon={<Package style={{ color: 'red', width: '36px', opacity: 1 }} />}
        title="Empty"
      />
    );
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    // jsdom normalizes `red` to rgb() form.
    expect(svg).toHaveStyle({ width: '36px', color: 'rgb(255, 0, 0)', opacity: '1' });
    // Untouched properties still come from the wrapper iconStyle.
    expect(svg).toHaveStyle({ height: '48px' });
  });

  it('renders string icon as text content (backward compat — emoji)', () => {
    render(<AppEmpty icon="📦" title="Empty" />);
    expect(screen.getByText('📦')).toBeInTheDocument();
  });

  it('renders string icon as text content (backward compat — text)', () => {
    // Consumers historically passed icon="calendar" (string) — span branch.
    render(<AppEmpty icon="calendar" title="Empty" />);
    const span = screen.getByText('calendar').closest('span');
    expect(span).toHaveAttribute('aria-hidden', 'true');
  });

  it('renders number icon as text content', () => {
    render(<AppEmpty icon={42} title="Empty" />);
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders without error when icon is null', () => {
    render(<AppEmpty icon={null} title="Empty" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Empty')).toBeInTheDocument();
  });

  it('renders without error when icon is omitted (undefined)', () => {
    render(<AppEmpty title="Empty" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Empty')).toBeInTheDocument();
  });

  it('renders without error when icon is a portal (excluded from component branch)', () => {
    // Portals have $$typeof but isValidElement(portal) is false; without the
    // explicit portal-type exclusion they would be misclassified as
    // components and <Icon /> would throw "Element type is invalid".
    const portal = createPortal(<svg data-testid="portal-icon" />, document.body);
    const { container } = render(<AppEmpty icon={portal} title="Empty" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Empty')).toBeInTheDocument();
    // The portal renders its children into the portal target (document.body),
    // not into the AppEmpty container.
    expect(container.querySelector('svg[data-testid="portal-icon"]')).toBeNull();
    expect(document.body.querySelector('svg[data-testid="portal-icon"]')).not.toBeNull();
  });
});

describe('AppEmpty — state contract (defaults, a11y wiring, passthrough)', () => {
  it('renders default title and description, with aria-describedby linked to the description id', () => {
    const { container } = render(<AppEmpty />);

    expect(screen.getByText('Нет данных')).toBeInTheDocument();
    expect(screen.getByText('Здесь пока нет данных для отображения.')).toBeInTheDocument();

    const status = screen.getByRole('status');
    const describedBy = status.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    const description = container.querySelector(`p#${CSS.escape(describedBy as string)}`);
    expect(description).not.toBeNull();
    expect(description).toHaveTextContent('Здесь пока нет данных для отображения.');
  });

  it('omits the description element and aria-describedby when description is falsy', () => {
    const { container } = render(<AppEmpty title="П" description="" />);
    const status = screen.getByRole('status');
    expect(status).not.toHaveAttribute('aria-describedby');
    expect(container.querySelector('p')).toBeNull();
  });

  it('renders the action inside the action slot', () => {
    render(
      <AppEmpty
        title="Нет записей"
        description="Данные появятся после загрузки."
        action={<button type="button">Обновить</button>}
      />
    );
    expect(screen.getByRole('button', { name: 'Обновить' })).toBeInTheDocument();
  });

  it('passes className and style through to the outer section', () => {
    const { container } = render(
      <AppEmpty title="П" className="extra-cls" style={{ margin: '10px' }} />
    );
    const section = container.querySelector('section') as HTMLElement;
    expect(section).toHaveClass('mac-app-empty');
    expect(section).toHaveClass('extra-cls');
    expect(section).toHaveStyle({ margin: '10px' });
    // Inner content keeps the minimal/md contract.
    const status = screen.getByRole('status');
    expect(status).toHaveStyle({ padding: '32px', gap: '16px' });
  });
});
