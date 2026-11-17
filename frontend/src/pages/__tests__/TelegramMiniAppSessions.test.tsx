import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
});
