import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../contexts/ThemeContext';
import TelegramMiniAppSessions from '../TelegramMiniAppSessions';
import i18n from '../../i18n';

const methods = vi.hoisted(() => ({
  list: vi.fn(), revoke: vi.fn(), revokeOthers: vi.fn(), logout: vi.fn(),
}));
vi.mock('../../api/telegramMiniAppSession', () => ({ telegramMiniAppSessions: methods }));

const rows = [
  { id: 'current', device_label: 'Windows', is_current: true },
  { id: 'other', device_label: 'Android', is_current: false },
].map((row) => ({
  ...row, created_at: '2026-11-16T10:00:00Z',
  last_active_at: '2026-11-16T10:00:00Z', expires_at: '2026-11-23T10:00:00Z',
}));
const translate = (key: string, params?: Record<string, unknown>) => `${key}${params?.device ? ` ${params.device}` : ''}`;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

const replacementRows = [{ ...rows[0], id: 'replacement', device_label: 'Synthetic B' }];
const sessionList = (sessions: typeof rows) => ({ sessions, total: sessions.length });

function renderLaunch(initData: string, onLoggedOut = vi.fn()) {
  const view = render(<ThemeProvider>
    <TelegramMiniAppSessions initData={initData} languageCode="ru" t={translate} onLoggedOut={onLoggedOut} />
  </ThemeProvider>);
  return {
    onLoggedOut,
    switchTo(nextInitData: string) {
      view.rerender(<ThemeProvider>
        <TelegramMiniAppSessions initData={nextInitData} languageCode="ru" t={translate} onLoggedOut={onLoggedOut} />
      </ThemeProvider>);
    },
  };
}

function setup(initData = 'synthetic-init-data', t = translate) {
  const onLoggedOut = vi.fn();
  render(<ThemeProvider>
    <TelegramMiniAppSessions initData={initData} languageCode="ru" t={t} onLoggedOut={onLoggedOut} />
  </ThemeProvider>);
  return onLoggedOut;
}

beforeEach(() => {
  vi.clearAllMocks();
  methods.list.mockResolvedValue({ sessions: rows, total: rows.length });
  methods.revoke.mockResolvedValue(undefined);
  methods.revokeOthers.mockResolvedValue(undefined);
  methods.logout.mockResolvedValue(undefined);
});

describe('patient devices workflow', () => {
  it('interpolates real translated dates and device labels without literal placeholders', async () => {
    const fixedT = i18n.getFixedT('ru');
    setup('synthetic-init-data', (key, params) => String(fixedT(
      'final.tgs_' + key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase(), params,
    )));
    expect(await screen.findByRole('button', {
      name: 'Завершить сеанс на устройстве Android',
    })).toBeInTheDocument();
    expect(screen.getAllByText(/^Вход:/)[0]).not.toHaveTextContent('{date}');
  });

  it('marks current device and confirms before revoking another device', async () => {
    setup();
    expect(await screen.findByText('sessionsCurrent')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'sessionsRevokeDevice Windows' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'sessionsRevokeDevice Android' }));
    expect(methods.revoke).not.toHaveBeenCalled();
    expect(screen.getByRole('group')).toHaveFocus();
    fireEvent.click(screen.getByRole('button', { name: 'sessionsCancel' }));
    expect(methods.revoke).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'sessionsRevokeDevice Android' }));
    fireEvent.click(screen.getByRole('button', { name: 'sessionsConfirm' }));
    await waitFor(() => expect(methods.revoke).toHaveBeenCalledWith('other', 'synthetic-init-data'));
    expect(await screen.findByText('sessionsDone')).toBeInTheDocument();
  });

  it('confirms revoking others and retains the current-session display', async () => {
    setup();
    await screen.findByText('sessionsCurrent');
    fireEvent.click(screen.getByRole('button', { name: 'sessionsRevokeOthers' }));
    expect(methods.revokeOthers).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'sessionsConfirm' }));
    await waitFor(() => expect(methods.revokeOthers).toHaveBeenCalledOnce());
    expect(screen.getByText('sessionsCurrent')).toBeInTheDocument();
  });

  it('logout needs confirmation and removes protected content through the shell callback', async () => {
    const loggedOut = setup();
    await screen.findByText('sessionsCurrent');
    fireEvent.click(screen.getByRole('button', { name: 'sessionsLogout' }));
    expect(methods.logout).not.toHaveBeenCalled();
    expect(screen.getByText('sessionsConfirmLogout')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'sessionsConfirm' }));
    await waitFor(() => expect(loggedOut).toHaveBeenCalledOnce());
  });

  it('shows safe error copy and offers retry without exposing a backend error', async () => {
    methods.list.mockRejectedValueOnce(new Error('sensitive-backend-payload'));
    setup();
    expect(await screen.findByRole('alert')).toHaveTextContent('sessionsFailed');
    expect(screen.queryByText('sensitive-backend-payload')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'sessionsRefresh' }));
    expect(await screen.findByText('sessionsCurrent')).toBeInTheDocument();
  });

  it('requires reopening in Telegram when opened through a scoped browser link', () => {
    setup('');
    expect(screen.getByText('sessionsUnavailable')).toBeInTheDocument();
    expect(methods.list).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'sessionsLogout' })).not.toBeInTheDocument();
  });

  it('hides the previous device list while a different launch loads', async () => {
    const replacement = deferred<ReturnType<typeof sessionList>>();
    methods.list.mockImplementation((initData: string) => (
      initData === 'synthetic-launch-a' ? Promise.resolve(sessionList(rows)) : replacement.promise
    ));
    const view = renderLaunch('synthetic-launch-a');
    await screen.findByText('Windows');

    view.switchTo('synthetic-launch-b');

    expect(screen.queryByText('Windows')).not.toBeInTheDocument();
    expect(screen.queryByText('Android')).not.toBeInTheDocument();
    await act(async () => replacement.resolve(sessionList(replacementRows)));
    expect(await screen.findByText('Synthetic B')).toBeInTheDocument();
  });

  it.each(['response', 'error'] as const)(
    'ignores an old manual reload %s after a different launch takes over',
    async (outcome) => {
      const oldReload = deferred<ReturnType<typeof sessionList>>();
      let oldCalls = 0;
      methods.list.mockImplementation((initData: string) => {
        if (initData !== 'synthetic-launch-a') return Promise.resolve(sessionList(replacementRows));
        oldCalls += 1;
        return oldCalls === 1 ? Promise.resolve(sessionList(rows)) : oldReload.promise;
      });
      const view = renderLaunch('synthetic-launch-a');
      await screen.findByText('Windows');
      fireEvent.click(screen.getByRole('button', { name: 'sessionsRefresh' }));
      view.switchTo('synthetic-launch-b');
      await screen.findByText('Synthetic B');

      await act(async () => {
        if (outcome === 'response') oldReload.resolve(sessionList(rows));
        else oldReload.reject(new Error('synthetic old request failure'));
      });

      expect(screen.getByText('Synthetic B')).toBeInTheDocument();
      expect(screen.queryByText('Windows')).not.toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    },
  );

  it('does not reload an old launch after its device action finishes late', async () => {
    const revoke = deferred<void>();
    methods.revoke.mockReturnValue(revoke.promise);
    methods.list.mockImplementation((initData: string) => Promise.resolve(
      sessionList(initData === 'synthetic-launch-a' ? rows : replacementRows),
    ));
    const view = renderLaunch('synthetic-launch-a');
    await screen.findByText('Windows');
    fireEvent.click(screen.getByRole('button', { name: 'sessionsRevokeDevice Android' }));
    fireEvent.click(screen.getByRole('button', { name: 'sessionsConfirm' }));
    view.switchTo('synthetic-launch-b');
    await screen.findByText('Synthetic B');

    await act(async () => revoke.resolve());

    expect(methods.list.mock.calls.map(([initData]) => initData)).toEqual([
      'synthetic-launch-a', 'synthetic-launch-b',
    ]);
    expect(screen.getByText('Synthetic B')).toBeInTheDocument();
  });

  it('does not log out a replacement launch when an old logout finishes late', async () => {
    const logout = deferred<void>();
    methods.logout.mockReturnValue(logout.promise);
    methods.list.mockImplementation((initData: string) => Promise.resolve(
      sessionList(initData === 'synthetic-launch-a' ? rows : replacementRows),
    ));
    const view = renderLaunch('synthetic-launch-a');
    await screen.findByText('Windows');
    fireEvent.click(screen.getByRole('button', { name: 'sessionsLogout' }));
    fireEvent.click(screen.getByRole('button', { name: 'sessionsConfirm' }));
    view.switchTo('synthetic-launch-b');
    await screen.findByText('Synthetic B');

    await act(async () => logout.resolve());

    expect(view.onLoggedOut).not.toHaveBeenCalled();
    expect(screen.getByText('Synthetic B')).toBeInTheDocument();
  });

  it('does not restore a revoked device when an earlier refresh finishes last', async () => {
    const oldRefresh = deferred<ReturnType<typeof sessionList>>();
    methods.list
      .mockResolvedValueOnce(sessionList(rows))
      .mockReturnValueOnce(oldRefresh.promise)
      .mockResolvedValueOnce(sessionList([rows[0]]));
    renderLaunch('synthetic-launch-a');
    await screen.findByText('Android');
    fireEvent.click(screen.getByRole('button', { name: 'sessionsRevokeDevice Android' }));
    fireEvent.click(screen.getByRole('button', { name: 'sessionsRefresh' }));
    fireEvent.click(screen.getByRole('button', { name: 'sessionsConfirm' }));
    await waitFor(() => expect(methods.list).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(screen.queryByText('Android')).not.toBeInTheDocument());

    await act(async () => oldRefresh.resolve(sessionList(rows)));

    expect(screen.getByText('Windows')).toBeInTheDocument();
    expect(screen.queryByText('Android')).not.toBeInTheDocument();
  });
});
