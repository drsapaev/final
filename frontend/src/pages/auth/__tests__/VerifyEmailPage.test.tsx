import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext';

const post = vi.hoisted(() => vi.fn());
vi.mock('../../../api/client', () => ({ api: { post } }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
import '../../../utils/emailVerificationBootstrap';
import VerifyEmailPage from '../VerifyEmailPage';
import { extractEmailVerificationCredential, takeEmailVerificationCredential } from '../../../utils/emailVerificationDeepLink';

const syntheticToken = `v1.${'v'.repeat(22)}.${'v'.repeat(22)}`;

function openPage(strict = false) {
  const page = <MemoryRouter><ThemeProvider><VerifyEmailPage /></ThemeProvider></MemoryRouter>;
  return render(strict ? <StrictMode>{page}</StrictMode> : page);
}

describe('email confirmation page', () => {
  beforeEach(() => { post.mockReset(); takeEmailVerificationCredential(); window.history.replaceState(null, '', '/'); });
  afterEach(async () => { cleanup(); await new Promise((resolve) => setTimeout(resolve, 0)); window.history.replaceState(null, '', '/'); });

  it('clears the URL before posting once across StrictMode remounts', async () => {
    window.history.replaceState(null, '', `/verify-email#token=${syntheticToken}`);
    extractEmailVerificationCredential();
    let finish!: (value: { data: { success: boolean } }) => void;
    post.mockImplementation(() => {
      expect(window.location.hash).toBe('');
      return new Promise((resolve) => { finish = resolve; });
    });
    openPage(true);
    expect(screen.getByRole('status')).toHaveTextContent('misc.ev_loading');
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith('/authentication/email-verification/confirm', { token: syntheticToken });
    finish({ data: { success: true } });
    expect(await screen.findByText('misc.ev_success')).toBeInTheDocument();
    expect(post).toHaveBeenCalledTimes(1);
  });

  it.each([[400, 'misc.ev_expired'], [422, 'misc.ev_expired'], [500, 'misc.ev_error'], [429, 'misc.ev_error']])('shows a safe status for response %s', async (status, expected) => {
    window.history.replaceState(null, '', `/verify-email#token=${syntheticToken}`);
    post.mockRejectedValue({ response: { status }, config: { data: syntheticToken } });
    openPage();
    expect(await screen.findByText(expected)).toBeInTheDocument();
    expect(screen.queryByText(syntheticToken)).toBeNull();
  });

  it('clears and verifies a new same-page hash once, without allowing an old response to win', async () => {
    window.history.replaceState(null, '', `/verify-email#token=${syntheticToken}`);
    let finishFirst!: (value: { data: { success: boolean } }) => void;
    post.mockImplementationOnce(() => new Promise((resolve) => { finishFirst = resolve; }));
    post.mockResolvedValueOnce({ data: { success: true } });
    openPage(true);
    expect(post).toHaveBeenCalledTimes(1);
    const next = `v1.${'n'.repeat(22)}.${'m'.repeat(22)}`;
    window.history.replaceState(null, '', `/verify-email#token=${next}`);
    fireEvent(window, new HashChangeEvent('hashchange'));
    expect(window.location.hash).toBe('');
    expect(await screen.findByText('misc.ev_success')).toBeInTheDocument();
    expect(post).toHaveBeenCalledTimes(2);
    expect(post).toHaveBeenLastCalledWith('/authentication/email-verification/confirm', { token: next });
    await act(async () => { finishFirst({ data: { success: false } }); });
    expect(screen.getByText('misc.ev_success')).toBeInTheDocument();
  });

  it('rejects a query-only or missing credential without a request', async () => {
    window.history.replaceState(null, '', `/verify-email?token=${syntheticToken}`);
    openPage();
    expect(await screen.findByText('misc.ev_expired')).toBeInTheDocument();
    expect(window.location.search).toBe('');
    expect(post).not.toHaveBeenCalled();
  });

  it('ignores the result of an unmounted page', async () => {
    window.history.replaceState(null, '', `/verify-email#token=${syntheticToken}`);
    let finish!: (value: { data: { success: boolean } }) => void;
    post.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    const { unmount } = openPage();
    unmount();
    finish({ data: { success: true } });
    await waitFor(() => expect(screen.queryByText('misc.ev_success')).toBeNull());
  });
});
