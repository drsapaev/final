import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import i18n from '@/i18n';
import Input from '../Input';

/**
 * Deterministic i18n contract for the macOS Input clear button (ported
 * Palette intent from #3391): the accessible name must come from the
 * common.clear locale key for the ACTIVE language — not from the retired
 * hardcoded string and not from the t() defaultValue fallback. Language is
 * pinned per test via i18n.changeLanguage (repo convention, see
 * Sidebar.navI18n.test.tsx) and the expected translated name is asserted
 * as an exact string, so old ("Clear input" in every language) and new
 * (localized) behavior can never pass at the same time.
 */
describe('Input', () => {
  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('renders a clear button for controlled clearable inputs and calls onClear (ru)', async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
    const onClear = vi.fn();

    render(
      <Input
        value="hello"
        onChange={() => {}}
        clearable
        onClear={onClear}
      />,
    );

    const clearButton = screen.getByRole('button', { name: 'Очистить' });
    expect(clearButton).toBeInTheDocument();

    fireEvent.click(clearButton);
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('localizes the clear-button accessible name from common.clear (en → Clear input)', async () => {
    await act(async () => {
      await i18n.changeLanguage('en');
    });

    render(
      <Input
        value="hello"
        onChange={() => {}}
        clearable
        onClear={() => {}}
      />,
    );

    expect(screen.getByRole('button', { name: 'Clear input' })).toBeInTheDocument();
  });

  it('keeps uz-Latn distinct from the defaultValue fallback (uz-Latn → Tozalash)', async () => {
    await act(async () => {
      await i18n.changeLanguage('uz-Latn');
    });

    render(
      <Input
        value="hello"
        onChange={() => {}}
        clearable
        onClear={() => {}}
      />,
    );

    expect(screen.getByRole('button', { name: 'Tozalash' })).toBeInTheDocument();
  });

  it('does not render a clear button when there is no value (ru)', async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });

    render(
      <Input
        value=""
        onChange={() => {}}
        clearable
        onClear={() => {}}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Очистить' })).not.toBeInTheDocument();
  });
});
