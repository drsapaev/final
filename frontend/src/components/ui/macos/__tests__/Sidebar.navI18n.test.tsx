import React from 'react';
import '@testing-library/jest-dom';
import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import i18n from '@/i18n';
import Sidebar from '../Sidebar';

vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    resolvedTheme: 'light',
    setTheme: () => {},
    toggleTheme: () => {},
  }),
}));

/**
 * PR-UI-19 (C-6): Sidebar resolves navigation labels through i18n.
 *
 * Architectural constraint (see plan §7 PR-UI-19): App.tsx computes
 * getRouteChromeState() without an i18n subscription, so translation MUST
 * happen at render time inside Sidebar (the only useTranslation() subscriber
 * in the chrome flow). These tests pin that contract:
 *  - labelKey items render through t() in the active language;
 *  - switching the language re-renders the sidebar reactively (no navigation
 *    action, no reload);
 *  - a key missing in every locale falls back to the item's fallback label
 *    (navigation never breaks).
 */
describe('PR-UI-19 (C-6): Sidebar labelKey i18n resolution', () => {
  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('renders a labelKey item through t() and switches language reactively', async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
    render(<Sidebar items={[{ id: 'queue', labelKey: 'nav.queue', icon: 'person.2' }]} activeItem="queue" />);

    expect(screen.getByRole('button', { name: 'Очередь' })).toBeInTheDocument();

    await act(async () => {
      await i18n.changeLanguage('en');
    });

    expect(screen.getByRole('button', { name: 'Queue' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Очередь' })).not.toBeInTheDocument();
  });

  it('keeps English and Uzbek nav translations distinct from ru', async () => {
    await act(async () => {
      await i18n.changeLanguage('en');
    });
    const { unmount } = render(
      <Sidebar items={[{ id: 'patients', labelKey: 'nav.patients', icon: 'person.2' }]} />
    );
    expect(screen.getByRole('button', { name: 'Patients' })).toBeInTheDocument();
    unmount();

    await act(async () => {
      await i18n.changeLanguage('uz-Latn');
    });
    render(<Sidebar items={[{ id: 'patients', labelKey: 'nav.patients', icon: 'person.2' }]} />);
    expect(screen.getByRole('button', { name: 'Bemorlar' })).toBeInTheDocument();
  });

  it('falls back to the fallback label when the key is missing everywhere', async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
    render(<Sidebar items={[{ id: 'legacy', labelKey: 'nav.nonexistent_key_for_test', label: 'Резерв' }]} />);
    expect(screen.getByRole('button', { name: 'Резерв' })).toBeInTheDocument();
  });

  it('renders plain-label items unchanged (backwards compatibility)', () => {
    render(<Sidebar items={[{ id: 'plain', label: 'Обычный пункт' }]} />);
    expect(screen.getByRole('button', { name: 'Обычный пункт' })).toBeInTheDocument();
  });
});
