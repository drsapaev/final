import React from 'react';
import '@testing-library/jest-dom';
import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import i18n from '@/i18n';
import MacOSPagination from '../MacOSPagination';

describe('MacOSPagination i18n accessibility', () => {
  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it.each([
    ['ru', 'Первая страница', 'Страница 2', 'Последняя страница'],
    ['en', 'First page', 'Page 2', 'Last page'],
    ['kk', 'Бірінші бет', 'Бет 2', 'Соңғы бет'],
    ['uz-Cyrl', 'Биринчи саҳифа', 'Саҳифа 2', 'Охирги саҳифа'],
    ['uz-Latn', 'Birinchi sahifa', 'Sahifa 2', 'Oxirgi sahifa'],
  ])('uses localized accessible names for %s', async (language, first, page, last) => {
    await act(async () => {
      await i18n.changeLanguage(language);
    });

    render(
      <MacOSPagination
        currentPage={2}
        totalPages={3}
        onPageChange={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: first })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: page })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: last })).toBeInTheDocument();
  });
});
