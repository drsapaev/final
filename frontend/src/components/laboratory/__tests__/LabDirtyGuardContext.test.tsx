import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, renderHook, screen, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  isLabRoutePath,
  LabDirtyGuardProvider,
  useGuardedLabNavigate,
  useLabDirtyGuard,
} from '../LabDirtyGuardContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

// PR 3351 (review round 2, P1): поведенческие тесты route-level leave guard —
// общий реестр источников на уровне App + guarded navigate + pending-блок.
// PR 3351 (review round 3): route identity вместо префикса /lab/*, pending
// -only блокировка через useGuardedLabNavigate, реактивный
// hasPendingOperations.

/** Постоянный (вне Routes) индикатор текущего пути. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

function LabPage({ onLeave }: { onLeave?: () => void }) {
  const navigate = useGuardedLabNavigate();
  return (
    <div>
      <button type="button" onClick={() => navigate('/profile')}>leave</button>
      <button type="button" onClick={() => navigate('/lab?tab=templates')}>stay-in-lab</button>
      <button type="button" onClick={() => navigate('/lab/results')}>leave-lab-results</button>
      <button type="button" onClick={() => navigate('/login', { onLeave })}>logout</button>
    </div>
  );
}

/** Держит ссылку на регистрацию для act-вызова после монтирования. */
function RegistrationBridge({
  registration,
  sourceIsDirty,
  sourceDiscard,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
  sourceIsDirty: () => boolean;
  sourceDiscard?: () => void;
}) {
  const guard = useLabDirtyGuard();
  // Рендер-присваивание: тест читает registration.current после render().
  registration.current = (source) => (
    guard.registerDirtySource({ ...source, discard: sourceDiscard })
  );
  return null;
}

function TestApp({
  registration,
  sourceIsDirty,
  sourceDiscard,
  onLeave,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
  sourceIsDirty: () => boolean;
  sourceDiscard?: () => void;
  onLeave?: () => void;
}) {
  return (
    <ThemeProvider>
      <MemoryRouter initialEntries={['/lab']}>
        <LabDirtyGuardProvider>
          <RegistrationBridge registration={registration} sourceIsDirty={sourceIsDirty} sourceDiscard={sourceDiscard} />
          <LocationProbe />
          <Routes>
            <Route path="/lab" element={<LabPage onLeave={onLeave} />} />
            <Route path="/profile" element={<div>profile page</div>} />
            <Route path="/login" element={<div>login page</div>} />
          </Routes>
        </LabDirtyGuardProvider>
      </MemoryRouter>
    </ThemeProvider>
  );
}

describe('LabDirtyGuardContext (PR 3351 route-level leave guard)', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('shares one guard registry between the panel sources and the app shell navigate', async () => {
    let reportDirty = false;
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};

    const first = render(
      <TestApp
        sourceIsDirty={() => reportDirty}
        registration={registration}
      />,
    );
    await act(async () => {
      registration.current?.({
        id: 'report',
        isDirty: () => reportDirty,
        save: vi.fn().mockResolvedValue(undefined),
      });
    });

    // Clean draft: уход с /lab проходит сразу, без диалога.
    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');

    // Dirty draft: тот же реестр виден guarded navigate — диалог, не переход.
    reportDirty = true;
    first.unmount();
    const second = render(
      <TestApp
        sourceIsDirty={() => reportDirty}
        registration={registration}
      />,
    );
    await act(async () => {
      registration.current?.({
        id: 'report',
        isDirty: () => reportDirty,
        save: vi.fn().mockResolvedValue(undefined),
      });
    });

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect(await screen.findByRole('dialog')).toBeVisible();

    // Переход ВНУТРИ /lab не блокируется даже при dirty-черновике —
    // смена tab не уничтожает draft (in-lab scope у панели).
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Отмена' }));
    await act(async () => { await Promise.resolve(); });
    fireEvent.click(screen.getByRole('button', { name: 'stay-in-lab' }));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByTestId('location')).toHaveTextContent('/lab?tab=templates');
    second.unmount();
  });

  it('keeps the user on /lab on cancel and runs onLeave only after confirmation', async () => {
    let reportDirty = true;
    const onLeave = vi.fn();
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};

    render(
      <TestApp
        sourceIsDirty={() => reportDirty}
        sourceDiscard={() => { reportDirty = false; }}
        registration={registration}
        onLeave={onLeave}
      />,
    );
    await act(async () => {
      registration.current?.({
        id: 'report',
        isDirty: () => reportDirty,
        save: vi.fn().mockResolvedValue(undefined),
      });
    });

    fireEvent.click(screen.getByRole('button', { name: 'logout' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeVisible();
    // onLeave (auth.clearToken) НЕ выполняется до подтверждения.
    expect(onLeave).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect(onLeave).not.toHaveBeenCalled();

    // Подтверждённый уход: discard → onLeave → переход на /login.
    fireEvent.click(screen.getByRole('button', { name: 'logout' }));
    const dialog2 = await screen.findByRole('dialog');
    fireEvent.click(within(dialog2).getByRole('button', { name: 'Выйти без сохранения' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });
    expect(onLeave).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('location')).toHaveTextContent('/login');
  });

  it('guardRouteLeave is blocked while a pending operation is in flight', () => {
    const { result } = renderHook(() => useLabDirtyGuard(), {
      wrapper: ({ children }) => (
        <MemoryRouter>
          <LabDirtyGuardProvider>{children}</LabDirtyGuardProvider>
        </MemoryRouter>
      ),
    });

    act(() => {
      result.current.setPendingOperationSources(['report']);
    });
    const leave = vi.fn();
    let started = true;
    act(() => {
      started = result.current.guardRouteLeave(leave);
    });
    // Переход заблокирован без диалога (pending-контракт route-level).
    expect(started).toBe(false);
    expect(leave).not.toHaveBeenCalled();
    expect(result.current.isDialogOpen).toBe(false);

    act(() => {
      result.current.setPendingOperationSources([]);
    });
    act(() => {
      started = result.current.guardRouteLeave(leave);
    });
    expect(started).toBe(true);
    expect(leave).toHaveBeenCalledTimes(1);
  });

  it('fallback (provider-less) keeps panel transitions working', () => {
    const { result } = renderHook(() => useLabDirtyGuard());
    expect(result.current.isProvided).toBe(false);
    const transition = vi.fn();
    let started = false;
    act(() => {
      started = result.current.guardTransition(transition);
    });
    expect(started).toBe(true);
    expect(transition).toHaveBeenCalledTimes(1);
  });

  // PR 3351 (review round 3, P1): route identity, а не префикс /lab/*.
  it('treats only the registered LabPanel route as staying in the lab', () => {
    // Точный маршрут реестра — единственный, что сохраняет панель.
    expect(isLabRoutePath('/lab')).toBe(true);
    // Deep-link каталога уведомлений НЕ зарегистрирован: wildcard уводит на
    // /not-found и размонтирует LabPanel — это уход.
    expect(isLabRoutePath('/lab/results')).toBe(false);
    expect(isLabRoutePath('/lab/results?critical=1')).toBe(false);
    // Прочие маршруты и legacy-алиасы — уход (redirect перемонтирует панель).
    expect(isLabRoutePath('/messages')).toBe(false);
    expect(isLabRoutePath('/profile')).toBe(false);
    expect(isLabRoutePath('/lab-panel')).toBe(false);
  });

  // PR 3351 (review round 4, P1): route identity разрешается ТЕМ же
  // matcher'ом, которым <Route path="/lab"> матчит реальные URL — иначе
  // URL, который роутер продолжает рендерить как LabPanel, guard считал бы
  // уходом и молча пропускал вооружение sentinel.
  it('resolves route identity with the React Router matcher (trailing slash, case)', () => {
    // Trailing-slash URL: App не канонизирует URL (Vercel отдаёт index.html
    // как есть), а React Router матчит '/lab/' маршруту '/lab' — панель
    // остаётся смонтированной, значит это НЕ уход с /lab.
    expect(isLabRoutePath('/lab/')).toBe(true);
    // Роутер регистронезависим по умолчанию (<Route> без caseSensitive) —
    // guard обязан разрешать '/Lab' так же, как роутер рендерит его в LabPanel.
    expect(isLabRoutePath('/Lab')).toBe(true);
    // Разные spellings — все ещё уход/не-маршрут LabPanel.
    expect(isLabRoutePath('/lab//results')).toBe(false);
    expect(isLabRoutePath('/lab-panel/')).toBe(false);
    expect(isLabRoutePath('/LAB/RESULTS')).toBe(false);
  });

  it('guards a navigation to the unregistered /lab/results deep-link (route identity)', async () => {
    let reportDirty = true;
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};

    render(
      <TestApp
        sourceIsDirty={() => reportDirty}
        sourceDiscard={() => { reportDirty = false; }}
        registration={registration}
      />,
    );
    await act(async () => {
      registration.current?.({
        id: 'report',
        isDirty: () => reportDirty,
        save: vi.fn().mockResolvedValue(undefined),
      });
    });

    // '/lab/results' не является маршрутом LabPanel — guard обязан спросить
    // пользователя, а не молча отдать URL wildcard-redirect'у.
    fireEvent.click(screen.getByRole('button', { name: 'leave-lab-results' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeVisible();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
  });

  // PR 3351 (review round 3, P1): pending-only операция блокирует уход через
  // useGuardedLabNavigate даже при полностью чистых черновиках.
  it('blocks a clean-draft leave while an operation is pending (pending-only guard)', async () => {
    // Wrapper монтирует и hook-children, и LabPage с LocationProbe —
    // guarded navigate кликается как реальный пользовательский сценарий.
    const wrapper = ({ children }: { children?: React.ReactNode }) => (
      <ThemeProvider>
        <MemoryRouter initialEntries={['/lab']}>
          <LabDirtyGuardProvider>
            <LocationProbe />
            {children}
            <Routes>
              <Route path="/lab" element={<LabPage />} />
              <Route path="/profile" element={<div>profile page</div>} />
              <Route path="/login" element={<div>login page</div>} />
            </Routes>
          </LabDirtyGuardProvider>
        </MemoryRouter>
      </ThemeProvider>
    );
    const { result } = renderHook(() => useLabDirtyGuard(), { wrapper });

    // Чистый черновик + pending-операция (clone чистого шаблона).
    act(() => {
      result.current.setPendingOperationSources(['template']);
    });
    expect(result.current.hasPendingOperations).toBe(true);

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    await act(async () => { await Promise.resolve(); });

    // Переход заблокирован БЕЗ диалога (pending-контракт), пользователь и
    // панель остаются на /lab.
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    // Операция завершилась: уход проходит сразу (clean, без диалога).
    act(() => {
      result.current.setPendingOperationSources([]);
    });
    expect(result.current.hasPendingOperations).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
  });

  // PR 3351 (review round 3, P1): pending флипает реактивный флаг контекста
  // (sentinel-хост перевзвешивается на 0↔n, а не только на dirty).
  it('publishes hasPendingOperations reactively across 0↔n flips only', () => {
    const { result } = renderHook(() => useLabDirtyGuard(), {
      wrapper: ({ children }) => (
        <MemoryRouter>
          <LabDirtyGuardProvider>{children}</LabDirtyGuardProvider>
        </MemoryRouter>
      ),
    });

    expect(result.current.hasPendingOperations).toBe(false);
    act(() => {
      result.current.setPendingOperationSources(['report']);
    });
    expect(result.current.hasPendingOperations).toBe(true);
    // Состав меняется, агрегат не флипает — значение то же (без ре-рендера).
    act(() => {
      result.current.setPendingOperationSources(['report', 'template']);
    });
    expect(result.current.hasPendingOperations).toBe(true);
    act(() => {
      result.current.setPendingOperationSources(['template']);
    });
    expect(result.current.hasPendingOperations).toBe(true);
    act(() => {
      result.current.setPendingOperationSources([]);
    });
    expect(result.current.hasPendingOperations).toBe(false);
  });
});
