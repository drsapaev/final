import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import i18n from '@/i18n';
import { ThemeProvider } from '@/contexts/ThemeContext';
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
const renderInput = (ui: React.ReactElement) => render(<ThemeProvider>{ui}</ThemeProvider>);

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

    renderInput(
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

    renderInput(
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

    renderInput(
      <Input
        value="hello"
        onChange={() => {}}
        clearable
        onClear={() => {}}
      />,
    );

    expect(screen.getByRole('button', { name: 'Tozalash' })).toBeInTheDocument();
  });

  it('localizes kk natively instead of the carried-over Russian string (kk → Тазалау)', async () => {
    await act(async () => {
      await i18n.changeLanguage('kk');
    });

    renderInput(
      <Input
        value="hello"
        onChange={() => {}}
        clearable
        onClear={() => {}}
      />,
    );

    // Exact native Kazakh string: the pre-R38-3 value was the Russian
    // "Очистить", so this assertion can never pass against it.
    expect(screen.getByRole('button', { name: 'Тазалау' })).toBeInTheDocument();
  });

  it('localizes uz-Cyrl natively instead of the carried-over Russian string (uz-Cyrl → Тозалаш)', async () => {
    await act(async () => {
      await i18n.changeLanguage('uz-Cyrl');
    });

    renderInput(
      <Input
        value="hello"
        onChange={() => {}}
        clearable
        onClear={() => {}}
      />,
    );

    // Exact native Cyrillic Uzbek string: the pre-R38-3 value was the
    // Russian "Очистить", so this assertion can never pass against it.
    expect(screen.getByRole('button', { name: 'Тозалаш' })).toBeInTheDocument();
  });

  it('does not render a clear button when there is no value (ru)', async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });

    renderInput(
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
