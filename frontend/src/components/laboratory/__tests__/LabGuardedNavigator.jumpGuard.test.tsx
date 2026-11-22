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

/**
 * LABGUARD-FE-001 (audit 3886, round 13) — fail-first.
 *
 * Multi-entry SPA-history jump (history.go(-2) и любые |n|>1) обходил
 * sentinel: pop приземлялся ЗА twin, «защитная ветка» молча разоружалась
 * и отдавала поп роутеру — панель размонтировалась и несохранённый
 * черновик терялся БЕЗ вопроса. Две поверхности:
 *   (A) публичный хук useGuardedLabNavigate принимал произвольные
 *       числовые дельты напрямую (navigate(n) без leave-контракта);
 *   (B) браузерный multi-entry POP при armed+dirty/pending откатывается
 *       (stateful rollback: go(+delta) к sentinel) с тем же guard-диалогом:
 *       подтверждение уходит на страницу прыжка, отмена оставляет
 *       пользователя и черновик на /lab.
 * Падает на до-фиксном коде: переход выполнялся молча, без диалога.
 *
 * История теста: [/health(idx0), /profile(idx1), /lab(idx2)] — SPA-записи
 * с router-idx, как в живом приложении; sentinel при dirty добавляет
 * [/lab-twin(idx2), /lab-sentinel(idx2)] поверх /lab.
 */

const SENTINEL_STATE_KEY = '__labLeaveGuardSentinel';

function sentinelMarkerPresent() {
  return Boolean(
    (window.history.state as Record<string, unknown> | null)?.[SENTINEL_STATE_KEY],
  );
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

function HealthPage() {
  const navigate = useNavigate();
  return (
    <div>
      health page
      <button type="button" onClick={() => navigate('/profile')}>to-profile</button>
    </div>
  );
}

function ProfilePage() {
  const navigate = useNavigate();
  return (
    <div>
      profile page
      <button type="button" onClick={() => navigate('/lab')}>enter-lab</button>
    </div>
  );
}

function LabPage() {
  const guardedNavigate = useGuardedLabNavigate();
  return (
    <div>
      lab page
      <button type="button" onClick={() => { guardedNavigate(-2); }}>hook-jump-back</button>
    </div>
  );
}

function RegistrationBridge({
  registration,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
}) {
  const guard = useLabDirtyGuard();
  registration.current = (source) => guard.registerDirtySource(source);
  return null;
}

function renderLabApp({
  registration,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
}) {
  window.history.replaceState(null, '', '/health');
  const view = render(
    <ThemeProvider>
      <BrowserRouter>
        <LabDirtyGuardProvider>
          <RegistrationBridge registration={registration} />
          <LocationProbe />
          <Routes>
            <Route path="/lab" element={<LabPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/health" element={<HealthPage />} />
          </Routes>
        </LabDirtyGuardProvider>
      </BrowserRouter>
    </ThemeProvider>,
  );
  // Стартовая запись получает router-idx явно (в живом приложении её
  // пишет BrowserRouter при инициализации) — twin-детекция и delta
  // отката зависят от idx на записи-предшественнике.
  window.history.replaceState(
    { ...(window.history.state as Record<string, unknown> ?? {}), idx: 0 },
    '',
    '/health',
  );
  return view;
}

/** [/health, /profile, /lab]: два SPA-шага до входа в лабораторию. */
async function walkToLab() {
  fireEvent.click(screen.getByRole('button', { name: 'to-profile' }));
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
  expect(screen.getByTestId('location')).toHaveTextContent('/profile');
  fireEvent.click(screen.getByRole('button', { name: 'enter-lab' }));
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
  expect(screen.getByTestId('location')).toHaveTextContent('/lab');
}

async function registerDirty(
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] },
  hooks: { save: () => Promise<void>; discard: () => void },
) {
  await act(async () => {
    registration.current?.({
      id: 'report',
      isDirty: () => true,
      save: hooks.save,
      discard: hooks.discard,
    });
  });
}

/** jsdom traverse — макротаска: после каждого history.go нужен свой барьер. */
async function historyTick() {
  await act(async () => {
    await new Promise((resolve) => { setTimeout(resolve, 0); });
    for (let i = 0; i < 8; i += 1) await Promise.resolve();
  });
}

/** Дожидаемся целевого location (rollback/save/discard — несколько traverse). */
async function waitLocation(expected: string, maxTries = 14) {
  for (let attempt = 0; attempt < maxTries; attempt += 1) {
    if ((screen.getByTestId('location').textContent ?? '').includes(expected)) return;
    await historyTick();
  }
}

describe('LABGUARD-FE-001 (A): guarded navigator refuses silent multi-step jumps', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('navigate(-2) through the hook at dirty asks first (dialog), then confirms', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    const save = vi.fn().mockResolvedValue(undefined);
    const discard = vi.fn();
    renderLabApp({ registration });
    await walkToLab();
    await registerDirty(registration, { save, discard });
    expect(sentinelMarkerPresent()).toBe(true);

    // До фикса: navigate(-2) выполнялся напрямую — молчаливый уход на
    // /profile без вопроса, черновик погибал.
    fireEvent.click(screen.getByRole('button', { name: 'hook-jump-back' }));
    await historyTick();

    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await waitLocation('/profile');
    expect(discard).toHaveBeenCalledTimes(1);
    expect(save).not.toHaveBeenCalled();
  });

  it('a CLEAN hook jump executes immediately without a dialog (unchanged semantics)', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration });
    await walkToLab();
    expect(sentinelMarkerPresent()).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'hook-jump-back' }));
    await waitLocation('/health');

    // История [/health, /profile, /lab]: -2 от /lab приземляется на /health.
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});

describe('LABGUARD-FE-001 (B): browser multi-entry POP rolls back to the sentinel', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('history.go(-2) at dirty rolls back to /lab and asks; Save lands on the jumped page', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    const save = vi.fn().mockResolvedValue(undefined);
    const discard = vi.fn();
    renderLabApp({ registration });
    await walkToLab();
    await registerDirty(registration, { save, discard });
    expect(sentinelMarkerPresent()).toBe(true);

    // Браузерный жест-прыжок на два шага назад (мимо twin): до фикса —
    // молчаливый переход на /profile, без диалога.
    window.history.go(-2);
    // Две фазы traverse: сначала прыжок на /profile (мимо twin), затем
    // откат к sentinel обратно на /lab — ждём ПО ОЧЕРЕДИ.
    await waitLocation('/profile');
    await waitLocation('/lab');

    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    const dialog = await screen.findByRole('dialog');
    expect(sentinelMarkerPresent()).toBe(true);

    fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить и перейти' }));
    await waitLocation('/profile');
    expect(save).toHaveBeenCalledTimes(1);
  });

  it('history.go(-2) at dirty: Cancel keeps the user and the draft on /lab', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    const save = vi.fn().mockResolvedValue(undefined);
    const discard = vi.fn();
    renderLabApp({ registration });
    await walkToLab();
    await registerDirty(registration, { save, discard });

    window.history.go(-2);
    await waitLocation('/profile');
    await waitLocation('/lab');

    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await historyTick();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect(discard).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
