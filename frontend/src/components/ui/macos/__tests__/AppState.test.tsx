// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React from 'react';
import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AppEmpty, AppError, AppLoading } from '../index';

describe('AppState primitives', () => {
  it('renders AppLoading as an accessible loading status', () => {
    render(<AppLoading description="Пожалуйста, подождите" />);

    expect(screen.getByRole('status', { name: /загрузка/i })).toBeInTheDocument();
    expect(screen.getByText('Пожалуйста, подождите')).toBeInTheDocument();
  });

  it('renders AppEmpty with neutral copy and an optional action', () => {
    render(
      <AppEmpty
        title="Нет записей"
        description="Данные появятся после загрузки."
        action={<button type="button">Обновить</button>}
      />,
    );

    expect(screen.getByLabelText('Нет записей')).toBeInTheDocument();
    expect(screen.getByText('Данные появятся после загрузки.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Обновить' })).toBeInTheDocument();
  });

  it('renders AppError as a calm operational alert', () => {
    render(
      <AppError
        description="Проверьте соединение."
        action={<button type="button">Повторить</button>}
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Не удалось загрузить данные');
    expect(screen.getByRole('alert')).toHaveTextContent('Проверьте соединение.');
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument();
  });
});
