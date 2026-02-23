import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Login from '../Login';
import { login } from '../../api/client';

vi.mock('../../api/client', () => ({
  login: vi.fn(),
  me: vi.fn(),
  setToken: vi.fn(),
}));

describe('Login Accessibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('binds labels to role, username and password fields', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    expect(screen.getByRole('combobox', { name: /выбрать роль|rolni tanlang|select role/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/логин|username|login/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/пароль|password|parol/i, { selector: 'input' })).toBeInTheDocument();
  });

  it('announces login errors via alert region', async () => {
    login.mockRejectedValueOnce(new Error('Неверные данные'));

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /войти|kirish|sign in/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(alert).toHaveTextContent('Неверные данные');

    const passwordField = screen.getByLabelText(/пароль|password|parol/i, { selector: 'input' });
    expect(passwordField).toHaveAttribute('aria-invalid', 'true');
    expect(passwordField).toHaveAttribute('aria-describedby', 'login-error');
  });
});
