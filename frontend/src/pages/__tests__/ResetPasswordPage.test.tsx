/** ResetPasswordPage — the missing destination of the email reset link (#2772). */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { StrictMode } from 'react';

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
import '../../utils/passwordResetBootstrap';
import { clearPasswordResetCredential, extractPasswordResetCredential, getPasswordResetCredential } from '../../utils/passwordResetDeepLink';

const ok = (data: unknown) => ({ status: 200, data });

afterEach(() => {
  cleanup();
  clearPasswordResetCredential();
  window.history.replaceState(null, '', '/');
  apiMock.mockReset();
});

const renderAt = (search: string) => {
  window.history.replaceState(null, '', `/reset-password${search}`);
  extractPasswordResetCredential();
  return render(
    <StrictMode><MemoryRouter initialEntries={[`/reset-password`]}>
      <ResetPasswordPage />
    </MemoryRouter></StrictMode>,
  );
};

describe('ResetPasswordPage', () => {
  it('validates the token, then posts confirm with token + new_password', async () => {
    apiMock
      .mockResolvedValueOnce(ok({ valid: true, time_left_minutes: 42 })) // validate-token
      .mockResolvedValueOnce(ok({ valid: true, time_left_minutes: 42 })) // StrictMode repeat
      .mockResolvedValueOnce(ok({ success: true })); // confirm

    renderAt('?token=GOODTOKEN');
    await screen.findByLabelText('final.fp_new_password');
    expect(window.location.search).toBe('');
    expect(apiMock).toHaveBeenCalledWith('/password-reset/validate-token', {
      headers: { 'X-Reset-Token': 'GOODTOKEN' },
    });

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
    apiMock.mockRejectedValue(new Error('404'));
    renderAt('?token=BAD');

    expect(await screen.findByText('final.rp_invalid_link')).toBeTruthy();
    // формы нет: заголовок h2 остаётся, но поля ввода отсутствуют
    expect(screen.queryByLabelText('final.fp_new_password')).toBeNull();
  });

  it('does not send a request when a link has duplicate tokens', async () => {
    renderAt('?token=FIRST&token=SECOND');
    expect(await screen.findByText('final.rp_invalid_link')).toBeTruthy();
    expect(window.location.search).toBe('');
    expect(apiMock).not.toHaveBeenCalled();
  });

  it('blocks submit while passwords mismatch or too short', async () => {
    apiMock.mockResolvedValue(ok({ valid: true }));
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

  it('counts Unicode code points like the API rather than UTF-16 units', async () => {
    apiMock.mockResolvedValue(ok({ valid: true }));
    renderAt('#token=GOODTOKEN');
    const pass = await screen.findByLabelText('final.fp_new_password');
    const confirm = screen.getByLabelText('final.fp_confirm_password');
    const submit = screen.getByText('final.fp_reset_password').closest('button') as HTMLButtonElement;
    fireEvent.change(pass, { target: { value: '😀😀😀😀' } });
    fireEvent.change(confirm, { target: { value: '😀😀😀😀' } });
    expect(submit.disabled).toBe(true);
    fireEvent.change(pass, { target: { value: '😀😀😀😀😀😀😀😀' } });
    fireEvent.change(confirm, { target: { value: '😀😀😀😀😀😀😀😀' } });
    expect(submit.disabled).toBe(false);
  });

  it.each([
    { detail: [{ type: 'string_too_short', input: 'SYNTHETIC_PRIVATE_PASSWORD' }] },
    { detail: 'SYNTHETIC_PRIVATE_PASSWORD' },
  ])('does not render untrusted error details', async ({ detail }) => {
    apiMock.mockImplementation((url: string) => (
      url.includes('/confirm')
        ? Promise.reject({ response: { status: 422, data: { detail } } })
        : Promise.resolve(ok({ valid: true }))
    ));
    renderAt('#token=GOODTOKEN');
    fireEvent.change(await screen.findByLabelText('final.fp_new_password'), { target: { value: 'NewPassw0rd!' } });
    fireEvent.change(screen.getByLabelText('final.fp_confirm_password'), { target: { value: 'NewPassw0rd!' } });
    fireEvent.click(screen.getByText('final.fp_reset_password'));
    expect(await screen.findByText('final.fp_reset_error')).toBeTruthy();
    expect(document.body.textContent).not.toContain('SYNTHETIC_PRIVATE_PASSWORD');
  });

  it('cleans and validates a replacement fragment while the page is mounted', async () => {
    apiMock.mockResolvedValue(ok({ valid: true }));
    renderAt('#token=FIRST');
    await screen.findByLabelText('final.fp_new_password');
    act(() => {
      window.location.hash = 'token=SECOND';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/password-reset/validate-token', {
      headers: { 'X-Reset-Token': 'SECOND' },
    }));
    expect(window.location.hash).toBe('');
  });

  it('cleans a legacy query reached by browser history navigation', async () => {
    apiMock.mockResolvedValue(ok({ valid: true }));
    renderAt('#token=FIRST');
    await screen.findByLabelText('final.fp_new_password');
    act(() => {
      window.history.replaceState(null, '', '/reset-password?token=SECOND');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/password-reset/validate-token', {
      headers: { 'X-Reset-Token': 'SECOND' },
    }));
    expect(window.location.search).toBe('');
  });

  it.each(['success', 'failure'])('ignores a late %s from a previous link', async (outcome) => {
    let finishOld: (value: unknown) => void = () => {};
    let failOld: (reason: unknown) => void = () => {};
    const oldConfirmation = new Promise((resolve, reject) => {
      finishOld = resolve;
      failOld = reject;
    });
    apiMock.mockImplementation((url: string) => (
      url.includes('/confirm') ? oldConfirmation : Promise.resolve(ok({ valid: true }))
    ));
    renderAt('#token=FIRST');
    const newPass = await screen.findByLabelText('final.fp_new_password');
    fireEvent.change(newPass, { target: { value: 'NewPassw0rd!' } });
    fireEvent.change(screen.getByLabelText('final.fp_confirm_password'), { target: { value: 'NewPassw0rd!' } });
    fireEvent.click(screen.getByText('final.fp_reset_password'));
    act(() => {
      window.location.hash = 'token=SECOND';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/password-reset/validate-token', {
      headers: { 'X-Reset-Token': 'SECOND' },
    }));
    expect((await screen.findByLabelText('final.fp_new_password') as HTMLInputElement).value).toBe('');
    expect((screen.getByLabelText('final.fp_confirm_password') as HTMLInputElement).value).toBe('');
    await act(async () => {
      if (outcome === 'success') finishOld(ok({ success: true }));
      else failOld({ response: { data: { detail: 'old-link-error' } } });
      await Promise.resolve();
    });
    expect(screen.queryByText('final.fp_success')).toBeNull();
    expect(screen.queryByText('old-link-error')).toBeNull();
    expect(screen.getByLabelText('final.fp_new_password')).toBeTruthy();
  });

  it.each(['invalid', 'failure'])('ignores late %s validation from an earlier link', async (outcome) => {
    let finishOld: (value: unknown) => void = () => {};
    let failOld: (reason: unknown) => void = () => {};
    const oldValidation = new Promise((resolve, reject) => {
      finishOld = resolve;
      failOld = reject;
    });
    apiMock.mockImplementation((_url: string, config: { headers: Record<string, string> }) => (
      config.headers['X-Reset-Token'] === 'FIRST' ? oldValidation : Promise.resolve(ok({ valid: true }))
    ));
    renderAt('#token=FIRST');
    act(() => {
      window.location.hash = 'token=SECOND';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    await screen.findByLabelText('final.fp_new_password');
    await act(async () => {
      if (outcome === 'invalid') finishOld(ok({ valid: false }));
      else failOld(new Error('old-link-error'));
      await Promise.resolve();
    });
    expect(screen.getByLabelText('final.fp_new_password')).toBeTruthy();
    expect(screen.queryByText('final.rp_invalid_link')).toBeNull();
  });

  it('does not let a confirmation from an unmounted view clear the next link', async () => {
    let finishOld: (value: unknown) => void = () => {};
    const oldConfirmation = new Promise((resolve) => { finishOld = resolve; });
    apiMock.mockImplementation((url: string) => (
      url.includes('/confirm') ? oldConfirmation : Promise.resolve(ok({ valid: true }))
    ));
    const previous = renderAt('#token=FIRST');
    fireEvent.change(await screen.findByLabelText('final.fp_new_password'), { target: { value: 'NewPassw0rd!' } });
    fireEvent.change(screen.getByLabelText('final.fp_confirm_password'), { target: { value: 'NewPassw0rd!' } });
    fireEvent.click(screen.getByText('final.fp_reset_password'));
    previous.unmount();
    renderAt('#token=SECOND');
    await screen.findByLabelText('final.fp_new_password');
    await act(async () => { finishOld(ok({ success: true })); await Promise.resolve(); });
    expect(getPasswordResetCredential()).toBe('SECOND');
    expect(screen.queryByText('final.fp_success')).toBeNull();
  });

  it('keeps the current submission when the route changes without changing the link', async () => {
    let finish: (value: unknown) => void = () => {};
    const confirmation = new Promise((resolve) => { finish = resolve; });
    apiMock.mockImplementation((url: string) => (
      url.includes('/confirm') ? confirmation : Promise.resolve(ok({ valid: true }))
    ));
    const ChangeLocation = () => {
      const navigate = useNavigate();
      return <button onClick={() => navigate('/reset-password?view=next')}>change location</button>;
    };
    window.history.replaceState(null, '', '/reset-password#token=FIRST');
    extractPasswordResetCredential();
    render(<MemoryRouter initialEntries={['/reset-password']}><ResetPasswordPage /><ChangeLocation /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText('final.fp_new_password'), { target: { value: 'NewPassw0rd!' } });
    fireEvent.change(screen.getByLabelText('final.fp_confirm_password'), { target: { value: 'NewPassw0rd!' } });
    fireEvent.click(screen.getByText('final.fp_reset_password'));
    fireEvent.click(screen.getByText('change location'));
    await act(async () => { finish(ok({ success: true })); await Promise.resolve(); });
    expect(await screen.findByText('final.fp_success')).toBeTruthy();
  });
});
