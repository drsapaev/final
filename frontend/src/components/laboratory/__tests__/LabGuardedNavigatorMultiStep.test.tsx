/**
 * LABGUARD-FE-001 / LABGUARD-FE-002 / LABGUARD-FE-003 (audit 3886, ledger
 * group «Lab dirty route-guard and browser navigation») — fail-first
 * regressions under a REAL BrowserRouter + window.history:
 *
 * **LABGUARD-FE-001 (P1):** a multi-entry history jump (browser go(-2) /
 * guarded navigate with |delta| > 1) leaps from the armed sentinel PAST the
 * twin onto a non-lab entry: the twin only absorbs a single step, so the
 * panel unmounts and the unsaved draft is lost without any dialog.
 *
 * **LABGUARD-FE-002 (P2):** query-only ('?tab=…') / hash-only ('#…')
 * navigation is misclassified as leaving lab — `new URL(to, origin)`
 * resolves the pathname against the ORIGIN ROOT instead of the current
 * href, so an in-lab UI change raises a destructive Save/Discard dialog.
 *
 * **LABGUARD-FE-003 (P2):** a second browser Back while a Logout/Profile
 * leave dialog is open overwrites the pending leave intent — confirming
 * the STILL-OPEN dialog silently reroutes to the Back target instead of
 * the dialog's own intent.
 *
 * Red-first: on the pre-fix source (1) guarded navigate(-2) traverses
 * without a dialog and lands on the non-lab entry; (2) window.history.go(-2)
 * silently lands on the non-lab entry with no recovery; (3) a query-only
 * navigation opens the destructive dialog; (4) a hash-only navigation opens
 * the destructive dialog; (5) Discard in the open dialog goes to the Back
 * target instead of the dialog's own /profile intent.
 */
import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  LabDirtyGuardProvider,
  useGuardedLabNavigate,
  useLabDirtyGuard,
} from '../LabDirtyGuardContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

const notifyMock = vi.hoisted(() => ({ info: vi.fn(), error: vi.fn(), success: vi.fn(), warning: vi.fn() }));

vi.mock('../../services/notify', () => ({
  __esModule: true,
  default: notifyMock,
  notify: notifyMock,
}));

const saveSpy = vi.fn().mockResolvedValue(undefined);
const discardSpy = vi.fn();

/** Постоянный (вне Routes) индикатор текущего пути. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search + location.hash}</div>;
}

/**
 * Реалистичная лабораторная страница: черновик — локальный state компонента
 * (размонтирование уничтожает его, как в реальных workbench-ах), dirty-источник
 * регистрируется из роут-скоупа и снимается при unmount.
 */
function LabPage({ withDraftSource = true }: { withDraftSource?: boolean }) {
  const [draft, setDraft] = React.useState('');
  const draftRef = React.useRef('');
  draftRef.current = draft;
  const guard = useLabDirtyGuard();
  const guardedNavigate = useGuardedLabNavigate();
  React.useEffect(() => {
    if (!withDraftSource) return undefined;
    return guard.registerDirtySource({
      id: 'report',
      isDirty: () => draftRef.current !== '',
      save: saveSpy,
      discard: () => { setDraft(''); discardSpy(); },
    });
  // guard-объект меняет идентичность на флипах диалога провайдера —
  // перерегистрация источника на каждый флип не нужна (регистратор стабилен).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guard.registerDirtySource, withDraftSource]);
  // Реальный контракт workbench-ов: уведомлять провайдер о каждом флипе
  // dirty-состояния (эффект без deps — на каждом рендере), иначе провайдер
  // не перевзвешивает sentinel.
  React.useEffect(() => {
    guard.notifyDirtyStateChange();
  });
  return (
    <div>
      <input
        aria-label="synthetic-draft"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
      <button type="button" onClick={() => guardedNavigate(-2)}>back-two</button>
      <button type="button" onClick={() => guardedNavigate('?tab=templates')}>query-tab</button>
      <button type="button" onClick={() => guardedNavigate('#results')}>hash-results</button>
      <button type="button" onClick={() => guardedNavigate('/profile')}>leave</button>
    </div>
  );
}

/** Стартовая не-lab страница: переход в /lab обычной router-навигацией. */
function HealthPage() {
  const navigate = useNavigate();
  return (
    <div>
      <button type="button" onClick={() => navigate('/lab')}>go-lab</button>
      <button type="button" onClick={() => navigate('/alpha')}>go-alpha</button>
    </div>
  );
}

/** Промежуточная не-lab страница (для контроля чистого многошагового перехода без sentinel-а). */
function AlphaPage() {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate('/lab')}>alpha-go-lab</button>;
}

function renderLabApp({ withDraftSource = true }: { withDraftSource?: boolean } = {}) {
  window.history.replaceState(null, '', '/health');
  return render(
    <ThemeProvider>
      <BrowserRouter>
        <LabDirtyGuardProvider>
          <LocationProbe />
          <Routes>
            <Route path="/health" element={<HealthPage />} />
            <Route path="/alpha" element={<AlphaPage />} />
            <Route path="/lab" element={<LabPage withDraftSource={withDraftSource} />} />
            <Route path="/profile" element={<div>profile page</div>} />
          </Routes>
        </LabDirtyGuardProvider>
      </BrowserRouter>
    </ThemeProvider>,
  );
}

/** Приходим на /lab через SPA-переход (router-декорированная запись под twin). */
async function arriveAtLab(dirty: { value?: string } = {}) {
  fireEvent.click(screen.getByRole('button', { name: 'go-lab' }));
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
  if (dirty.value !== undefined) {
    fireEvent.change(screen.getByLabelText('synthetic-draft'), { target: { value: dirty.value } });
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });
  }
}

/** Приходим на /lab через /alpha: 2 записи под текущей даже без sentinel-а. */
async function arriveAtLabViaAlpha() {
  fireEvent.click(screen.getByRole('button', { name: 'go-alpha' }));
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
  fireEvent.click(screen.getByRole('button', { name: 'alpha-go-lab' }));
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
}

async function settle(ms: number) {
  await act(async () => {
    await new Promise((resolve) => { setTimeout(resolve, ms); });
  });
}

async function confirmDialog(action: 'discard' | 'cancel') {
  const dialog = screen.getByRole('dialog');
  const label = action === 'discard' ? 'Выйти без сохранения' : 'Отмена';
  fireEvent.click(within(dialog).getByRole('button', { name: label }));
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
}

describe('LABGUARD-FE-001 — multi-entry history jumps cannot skip the lab guard', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('guarded navigate(-2) with a dirty draft opens the leave dialog and keeps the user on /lab (pre-fix: silent traversal, panel unmounted)', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect((screen.getByLabelText('synthetic-draft') as HTMLInputElement).value).toBe('42');

    // Многошаговая дельта через guarded navigator: предварительное решение,
    // а не молчаливый traversal мимо twin-записи.
    fireEvent.click(screen.getByRole('button', { name: 'back-two' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    // Отмена: черновик и позиция сохранены — перехода не было.
    await confirmDialog('cancel');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect((screen.getByLabelText('synthetic-draft') as HTMLInputElement).value).toBe('42');
    expect(discardSpy).not.toHaveBeenCalled();
  });

  it('after confirming the multi-step leave, the traversal lands on the intended 2-back entry', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });

    fireEvent.click(screen.getByRole('button', { name: 'back-two' }));
    await screen.findByRole('dialog');

    await confirmDialog('discard');
    await settle(80);

    expect(screen.getByTestId('location')).toHaveTextContent('/health');
    expect(discardSpy).toHaveBeenCalledTimes(1);
  });

  it('browser history.go(-2) with a dirty draft: the user stays on /lab pending an explicit Save/Discard decision; Cancel preserves the field value (pre-fix: silent loss on /health)', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });

    await act(async () => { window.history.go(-2); });
    // Отложенное решение срабатывает после CONFIRMED_LEAVE_COMPLETION_TIMEOUT_MS.
    await settle(450);

    // Пользователь остался в лаборатории: многошаговый прыжок развёрнут
    // на lab-запись, панель пережила прыжок.
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    // Черновок цел — решение спрашивается явно, а не теряется молча.
    const dialog = await screen.findByRole('dialog');
    expect((screen.getByLabelText('synthetic-draft') as HTMLInputElement).value).toBe('42');

    // Отмена: позиция и черновик сохранены.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect((screen.getByLabelText('synthetic-draft') as HTMLInputElement).value).toBe('42');
    expect(discardSpy).not.toHaveBeenCalled();
  });

  it('confirming the recovered multi-step jump lands on the captured target entry', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });

    await act(async () => { window.history.go(-2); });
    await settle(450);

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await settle(80);

    // Подтверждение выполняет ЗАХВАЧЕННУЮ цель прыжка — /health.
    expect(screen.getByTestId('location')).toHaveTextContent('/health');
    expect(discardSpy).toHaveBeenCalledTimes(1);
  });

  it('control: a clean state traverses immediately without a dialog', async () => {
    renderLabApp({ withDraftSource: false });
    await arriveAtLabViaAlpha();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    fireEvent.click(screen.getByRole('button', { name: 'back-two' }));
    await settle(80);

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('location')).toHaveTextContent('/health');
  });
});

describe('LABGUARD-FE-002 — query-only and hash-only navigation stays in-lab', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('a query-only "?tab=templates" navigation does not raise the destructive dialog (pre-fix: Save/Discard for an in-lab change)', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });

    fireEvent.click(screen.getByRole('button', { name: 'query-tab' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab?tab=templates');
    expect((screen.getByLabelText('synthetic-draft') as HTMLInputElement).value).toBe('42');
  });

  it('a hash-only "#results" navigation does not raise the destructive dialog', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });

    fireEvent.click(screen.getByRole('button', { name: 'hash-results' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab#results');
    expect((screen.getByLabelText('synthetic-draft') as HTMLInputElement).value).toBe('42');
  });

  it('control: an absolute "/profile" leave still opens the guard dialog', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
  });
});

describe('LABGUARD-FE-003 — a pending leave intent cannot be silently replaced', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('a second browser Back during an open leave dialog keeps the dialog intent: Discard still goes to /profile (pre-fix: rerouted to the Back target)', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });

    // Открываем leave-диалог (интент: /profile).
    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    // Browser Back ДО подтверждения: вытесняет twin, но НЕ должен подменять
    // интент открытого диалога. Треверсал jsdom асинхронен — ждём МАКРОтаск,
    // чтобы popstate гарантированно прибыл (и twin-ветка перевзвесила
    // sentinel) ДО подтверждения диалога.
    await act(async () => { window.history.back(); });
    await settle(50);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await confirmDialog('discard');
    await settle(80);

    // Подтверждение выполнило ИСХОДНЫЙ интент диалога — /profile, а не цель
    // перехваченного Back-а.
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
    expect(discardSpy).toHaveBeenCalledTimes(1);
  });

  it('Cancel after the interleaved Back preserves the draft and stays on /lab', async () => {
    renderLabApp();
    await arriveAtLab({ value: '42' });

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    await act(async () => { window.history.back(); });
    await settle(50);

    await confirmDialog('cancel');
    await settle(80);

    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect((screen.getByLabelText('synthetic-draft') as HTMLInputElement).value).toBe('42');
    expect(discardSpy).not.toHaveBeenCalled();
  });
});
