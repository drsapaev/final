/** ResetPasswordPage — the missing destination of the email reset link (#2772). */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));

vi.mock('../../api/client', () => ({
  api: Object.assign(apiMock, {
    get: apiMock,
    post: apiMock,
  }),
}));

vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import ResetPasswordPage from '../ResetPasswordPage';

const ok = (data: unknown) => ({ status: 200, data });

afterEach(() => {
  cleanup();
  apiMock.mockReset();
});

const renderAt = (search: string) =>
  render(
    <MemoryRouter initialEntries={[`/reset-password${search}`]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  );

describe('ResetPasswordPage', () => {
  it('validates the token, then posts confirm with token + new_password', async () => {
    apiMock
      .mockResolvedValueOnce(ok({ valid: true, time_left_minutes: 42 })) // validate-token
      .mockResolvedValueOnce(ok({ success: true })); // confirm

    renderAt('?token=GOODTOKEN');
    await screen.findByLabelText('final.fp_new_password');

    fireEvent.change(screen.getByLabelText('final.fp_new_password'), {
      target: { value: 'NewPassw0rd!' },
    });
    fireEvent.change(screen.getByLabelText('final.fp_confirm_password'), {
      target: { value: 'NewPassw0rd!' },
    });
    fireEvent.click(screen.getByText('final.fp_reset_password'));

    await waitFor(() => {
      const confirmCall = apiMock.mock.calls.find(
        ([url]) => String(url).includes('/password-reset/confirm'),
      );
      expect(confirmCall).toBeTruthy();
      expect(confirmCall?.[1]).toEqual({
        token: 'GOODTOKEN',
        new_password: 'NewPassw0rd!',
      });
    });
    expect(await screen.findByText('final.fp_success')).toBeTruthy();
  });

  it('surfaces the server detail reason on 400 confirm', async () => {
    apiMock
      .mockResolvedValueOnce(ok({ valid: true }))
      .mockRejectedValueOnce({
        response: { status: 400, data: { detail: 'Новый пароль должен отличаться от текущего' } },
      });

    renderAt('?token=GOODTOKEN');
    const pass = await screen.findByLabelText('final.fp_new_password');
    const conf = screen.getByLabelText('final.fp_confirm_password');
    fireEvent.change(pass, { target: { value: 'BrandNewPass1' } });
    fireEvent.change(conf, { target: { value: 'BrandNewPass1' } });
    fireEvent.click(screen.getByText('final.fp_reset_password'));

    expect(
      await screen.findByText('Новый пароль должен отличаться от текущего'),
    ).toBeTruthy();
  });

  it('shows invalid-link screen when token is expired/unknown', async () => {
    apiMock.mockRejectedValueOnce(new Error('404'));
    renderAt('?token=BAD');

    expect(await screen.findByText('final.rp_invalid_link')).toBeTruthy();
    // формы нет: заголовок h2 остаётся, но поля ввода отсутствуют
    expect(screen.queryByLabelText('final.fp_new_password')).toBeNull();
  });

  it('blocks submit while passwords mismatch or too short', async () => {
    apiMock.mockResolvedValueOnce(ok({ valid: true }));
    renderAt('?token=GOODTOKEN');
    await screen.findByLabelText('final.fp_new_password');

    const pass = screen.getByLabelText('final.fp_new_password') as HTMLInputElement;
    const conf = screen.getByLabelText('final.fp_confirm_password') as HTMLInputElement;
    const btn = screen.getByText('final.fp_reset_password').closest('button') as HTMLButtonElement;

    fireEvent.change(pass, { target: { value: 'short' } });
    fireEvent.change(conf, { target: { value: 'short' } });
    expect(btn.disabled).toBe(true); // <8 chars

    fireEvent.change(pass, { target: { value: 'LongPassw0rd' } });
    expect(btn.disabled).toBe(true); // mismatch

    fireEvent.change(conf, { target: { value: 'LongPassw0rd' } });
    expect(btn.disabled).toBe(false);
  });
});
