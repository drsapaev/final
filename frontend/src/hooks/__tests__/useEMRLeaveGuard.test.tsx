import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import { LabDirtyGuardProvider, useGuardedLabNavigate, useLabDirtyGuard } from '../../components/laboratory/LabDirtyGuardContext';
import { useEMRLeaveGuard } from '../useEMRLeaveGuard';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * RETRO-3971-04 residual (post-merge re-review of #4009): route-level
 * acceptance for the EMR leave guard.
 *
 * A dirty clinical draft must survive an SPA leave decision:
 *   - the leave is intercepted by the shared App-level guard dialog
 *     (Stay / Retry / Discard), not by a fire-and-forget unmount flush;
 *   - «Save and leave» AWAITS the server response of the CURRENT visit
 *     and only a genuinely acknowledged draft save performs the
 *     transition — a 409 conflict, a FINALIZED_STATE, an access denial,
 *     a stale-visit drop (null) or a transport failure leaves the user
 *     on the route with the draft intact and the dialog still actionable
 *     (Retry/Discard stay available);
 *   - a pending (in-flight) autosave blocks the leave until it settles;
 *   - «Discard» is an explicit reload of the server baseline;
 *   - unmounting the editor unregisters the source;
 *   - read-only observers (enabled=false) never register.
 */

type SaveEMRMock = Mock<(opts?: Record<string, unknown>) => Promise<unknown>>;
type ReloadMock = Mock<() => Promise<unknown>>;

interface HarnessConfig {
  dirty: boolean;
  saving: boolean;
  enabled: boolean;
  saveEMR: SaveEMRMock;
  reload: ReloadMock;
}

function makeConfig(overrides: Partial<HarnessConfig> = {}): HarnessConfig {
  return {
    dirty: false,
    saving: false,
    enabled: true,
    saveEMR: vi.fn<(opts?: Record<string, unknown>) => Promise<unknown>>(
      async () => ({ status: 'in_progress', row_version: 5 }),
    ),
    reload: vi.fn<() => Promise<unknown>>(async () => undefined),
    ...overrides,
  };
}

/** Постоянный (вне Routes) индикатор текущего пути. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

/** Захват агрегированного dirty-состояния общего реестра. */
function DirtyProbe() {
  const guard = useLabDirtyGuard();
  return <div data-testid="guard-dirty">{String(guard.hasDirtySources())}</div>;
}

function EmrEditor({ config }: { config: HarnessConfig }) {
  const [dirty, setDirty] = React.useState(config.dirty);
  const [saving, setSaving] = React.useState(config.saving);
  useEMRLeaveGuard({
    visitId: 42,
    isDirty: dirty,
    isSaving: saving,
    saveEMR: config.saveEMR,
    reloadFromServer: config.reload,
    enabled: config.enabled,
  });
  return (
    <div>
      <div>emr editor</div>
      <button type="button" onClick={() => setDirty((v) => !v)}>toggle-dirty</button>
      <button type="button" onClick={() => setSaving((v) => !v)}>toggle-saving</button>
    </div>
  );
}

function EmrRoute({ config }: { config: HarnessConfig }) {
  const [editorMounted, setEditorMounted] = React.useState(true);
  const navigate = useGuardedLabNavigate();
  return (
    <div>
      {editorMounted ? <EmrEditor config={config} /> : <div>no editor</div>}
      <button type="button" onClick={() => setEditorMounted((v) => !v)}>toggle-editor</button>
      <button type="button" onClick={() => navigate('/profile')}>leave</button>
    </div>
  );
}

function ProfilePage() {
  const navigate = useGuardedLabNavigate();
  return (
    <div>
      profile page
      <button type="button" onClick={() => navigate('/doctor/dermatology')}>to-derm</button>
    </div>
  );
}

function TestApp({ config }: { config: HarnessConfig }) {
  return (
    <ThemeProvider>
      <MemoryRouter initialEntries={['/doctor/dermatology']}>
        <LabDirtyGuardProvider>
          <DirtyProbe />
          <LocationProbe />
          <Routes>
            <Route path="/doctor/dermatology" element={<EmrRoute config={config} />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Routes>
        </LabDirtyGuardProvider>
      </MemoryRouter>
    </ThemeProvider>
  );
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
}

describe('useEMRLeaveGuard (RETRO-3971-04 residual route-level acceptance)', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('a dirty SPA leave opens the guard dialog; Stay keeps the editor mounted with the draft', async () => {
    const config = makeConfig({ dirty: true });
    render(<TestApp config={config} />);
    await settle();
    expect(screen.getByTestId('guard-dirty')).toHaveTextContent('true');

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    const dialog = await screen.findByRole('dialog');
    // Навигация НЕ уничтожила редактор: путь прежний, источник жив.
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(screen.getByText('emr editor')).toBeInTheDocument();
    expect(config.saveEMR).not.toHaveBeenCalled();

    // Stay (Отмена): пользователь и черновик остаются на месте.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByTestId('guard-dirty')).toHaveTextContent('true');
  });

  it('Save-and-leave waits for the server ack; an acknowledged draft save performs the transition', async () => {
    const config = makeConfig({ dirty: true });
    render(<TestApp config={config} />);
    await settle();

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить и перейти' }));
    await settle();

    // Сохранение выполнялось как DRAFT-автосейв текущего визита.
    expect(config.saveEMR).toHaveBeenCalledWith({ isDraft: true });
    // Переход выполнен ТОЛЬКО после серверного ack.
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it.each([
    ['a 409 version conflict', () => ({ conflict: true, row_version: 4 })],
    ['a FINALIZED_STATE 409', () => ({ finalized: true, row_version: 4 })],
    ['an access denial', () => ({ accessDenied: true, status: 403 })],
    ['a signed rejection', () => ({ signed: true })],
    ['a stale-visit drop (null result)', () => null],
    ['a transport failure', () => { throw new Error('network down'); }],
  ])('Save-and-leave on %s keeps the user on the route with the draft and the dialog actionable', async (_name, makeResult) => {
    const config = makeConfig({ dirty: true });
    config.saveEMR.mockImplementation(async () => makeResult());
    render(<TestApp config={config} />);
    await settle();

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить и перейти' }));
    await settle();

    // Ни перехода, ни «успеха»: редактор на месте, черновик жив, диалог открыт.
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(screen.getByText('emr editor')).toBeInTheDocument();
    expect(screen.getByTestId('guard-dirty')).toHaveTextContent('true');
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    // RETRY: сервер восстановился — повторное «Сохранить и перейти» уходит.
    config.saveEMR.mockImplementation(async () => ({ status: 'in_progress', row_version: 6 }));
    const retryDialog = screen.getByRole('dialog');
    fireEvent.click(within(retryDialog).getByRole('button', { name: 'Сохранить и перейти' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('Discard performs an explicit reload to the server baseline and performs the transition', async () => {
    const config = makeConfig({ dirty: true });
    render(<TestApp config={config} />);
    await settle();

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await settle();

    expect(config.reload).toHaveBeenCalledTimes(1);
    expect(config.saveEMR).not.toHaveBeenCalled();
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
  });

  it('a pending (in-flight) autosave blocks the SPA leave until it settles', async () => {
    const config = makeConfig({ saving: true });
    render(<TestApp config={config} />);
    await settle();
    expect(screen.getByTestId('guard-dirty')).toHaveTextContent('false');

    // Pending-only: документ чист, но автосейв в полёте — уход заблокирован.
    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    // Операция завершилась — переход выполняется без диалога.
    fireEvent.click(screen.getByRole('button', { name: 'toggle-saving' }));
    await settle();
    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
  });

  it('unmounting the editor removes the draft source from the shared registry', async () => {
    const config = makeConfig({ dirty: true });
    render(<TestApp config={config} />);
    await settle();
    expect(screen.getByTestId('guard-dirty')).toHaveTextContent('true');

    // Редактор уходит (подтверждённый переход/смена контекста) — источник
    // снялся из общего реестра: повторный SPA-уход больше не блокируется.
    fireEvent.click(screen.getByRole('button', { name: 'toggle-editor' }));
    await settle();
    expect(screen.getByTestId('guard-dirty')).toHaveTextContent('false');

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
    expect(config.saveEMR).not.toHaveBeenCalled();
  });

  it('read-only observers (enabled=false) never register a draft source', async () => {
    const config = makeConfig({ dirty: true, enabled: false });
    render(<TestApp config={config} />);
    await settle();
    expect(screen.getByTestId('guard-dirty')).toHaveTextContent('false');

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
    expect(config.saveEMR).not.toHaveBeenCalled();
  });
});
