import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  LabDirtyGuardProvider,
  useGuardedLabNavigate,
  useLabDirtyGuard,
} from '../LabDirtyGuardContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * PR 3351 (review round 5, P1): history-контракт guarded navigator-а под
 * НАСТОЯЩим window.history (BrowserRouter) — в отличие от
 * LabDirtyGuardContext.test.tsx (MemoryRouter, sentinel пассивен).
 *
 * In-lab переход (с маршрута LabPanel на тот же маршрут LabPanel) через
 * guarded navigator НЕ создаёт history-записей:
 *   - при вооружённом sentinel — replace с сохранением маркера
 *     (push поверх sentinel ломал бы дельту -2 подтверждённого ухода:
 *     -2 приземлялся на устаревшую помеченную копию вместо реальной
 *     предыдущей страницы);
 *   - до вооружения sentinel (чистый черновик) — replace тоже: push
 *     оставлял бы вторую /lab-запись, и последующий arm поверх неё
 *     направлял бы -2 на /lab-копию.
 * Идентичный URL — полный no-op (без router-перехода и без нового
 * location.key). Подтверждённый уход заменяет sentinel-запись (replace)
 * и завершается на не-lab маршруте.
 */

const SENTINEL_STATE_KEY = '__labLeaveGuardSentinel';

function sentinelMarkerPresent() {
  return Boolean(
    (window.history.state as Record<string, unknown> | null)?.[SENTINEL_STATE_KEY],
  );
}

/** Постоянный (вне Routes) индикатор текущего пути. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

/** location.key меняется на каждом router-переходе — детектор no-op. */
function LocationKeyProbe() {
  const location = useLocation();
  return <div data-testid="location-key">{location.key}</div>;
}

function LabNavPage() {
  const navigate = useGuardedLabNavigate();
  const location = useLocation();
  const currentPath = location.pathname + location.search;
  return (
    <div>
      <button type="button" onClick={() => navigate('/lab?tab=templates')}>to-lab-templates</button>
      <button type="button" onClick={() => navigate(currentPath)}>same-url</button>
      <button type="button" onClick={() => navigate('/profile')}>leave</button>
    </div>
  );
}

/** Держит ссылку на регистрацию для act-вызова после монтирования. */
function RegistrationBridge({
  registration,
  sourceDiscard,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
  sourceDiscard?: () => void;
}) {
  const guard = useLabDirtyGuard();
  // Рендер-присваивание: тест читает registration.current после render().
  registration.current = (source) => (
    guard.registerDirtySource({ ...source, discard: sourceDiscard })
  );
  return null;
}

function renderLabApp({
  registration,
  sourceDiscard,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
  sourceDiscard?: () => void;
}) {
  // Текущая запись — '/lab' без router-состояния (как прямой вход).
  window.history.replaceState(null, '', '/lab');
  return render(
    <ThemeProvider>
      <BrowserRouter>
        <LabDirtyGuardProvider>
          <RegistrationBridge
            registration={registration}
            sourceDiscard={sourceDiscard}
          />
          <LocationProbe />
          <LocationKeyProbe />
          <Routes>
            <Route path="/lab" element={<LabNavPage />} />
            <Route path="/profile" element={<div>profile page</div>} />
          </Routes>
        </LabDirtyGuardProvider>
      </BrowserRouter>
    </ThemeProvider>,
  );
}

async function registerDirtySource(
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] },
) {
  await act(async () => {
    registration.current?.({
      id: 'report',
      isDirty: () => true,
      save: vi.fn().mockResolvedValue(undefined),
      discard: vi.fn(),
    });
  });
}

describe('Lab guarded navigator history contract (PR 3351 review round 5)', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('replaces (never pushes) an in-lab navigation while the sentinel is armed', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration, sourceIsDirty: () => true });
    await registerDirtySource(registration);

    // Sentinel вооружён: текущая запись помечена.
    expect(sentinelMarkerPresent()).toBe(true);
    const armedLength = window.history.length;

    // In-lab переход (Header brand / Command Palette → canonical /lab):
    // replace, не push — history не растёт.
    fireEvent.click(screen.getByRole('button', { name: 'to-lab-templates' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });

    expect(screen.getByTestId('location')).toHaveTextContent('/lab?tab=templates');
    expect(window.history.length).toBe(armedLength);
    // Декоратор replaceState сохранил маркер sentinel синхронно.
    expect(sentinelMarkerPresent()).toBe(true);
  });

  it('is a full no-op for a navigation to the already-open lab URL', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration, sourceIsDirty: () => true });
    await registerDirtySource(registration);

    fireEvent.click(screen.getByRole('button', { name: 'to-lab-templates' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });
    expect(screen.getByTestId('location')).toHaveTextContent('/lab?tab=templates');

    // Навигация на уже открытый URL (brand на canonical /lab при том же
    // адресе) — полный no-op: ни router-перехода (location.key прежний),
    // ни history-записи.
    const keyBefore = screen.getByTestId('location-key').textContent;
    const lengthBefore = window.history.length;
    fireEvent.click(screen.getByRole('button', { name: 'same-url' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });

    expect(screen.getByTestId('location')).toHaveTextContent('/lab?tab=templates');
    expect(screen.getByTestId('location-key').textContent).toBe(keyBefore);
    expect(window.history.length).toBe(lengthBefore);
    expect(sentinelMarkerPresent()).toBe(true);
  });

  it('replaces an in-lab navigation even before the sentinel is armed (clean draft)', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    // Чистый черновик: sentinel не вооружается, но вторая /lab-запись всё
    // равно не должна создаваться — иначе последующий arm поверх неё
    // направил бы подтверждённый -2 на /lab-копию.
    renderLabApp({ registration });
    await act(async () => {
      await Promise.resolve();
    });
    expect(sentinelMarkerPresent()).toBe(false);

    const lengthBefore = window.history.length;
    fireEvent.click(screen.getByRole('button', { name: 'to-lab-templates' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });

    expect(screen.getByTestId('location')).toHaveTextContent('/lab?tab=templates');
    expect(window.history.length).toBe(lengthBefore);
  });

  it('a confirmed leave replaces the sentinel entry and lands on the non-lab route', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration, sourceIsDirty: () => true });
    await registerDirtySource(registration);
    expect(sentinelMarkerPresent()).toBe(true);
    const armedLength = window.history.length;

    // Уход с /lab при dirty — guard-диалог, не молчаливый переход.
    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    // Подтверждение: sentinel-запись ЗАМЕНЯЕТСЯ целью (replace) — Back со
    // страницы профиля вернётся на реальный /lab без дубля.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });

    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
    expect(window.history.length).toBe(armedLength);
    // Запись назначения не наследует sentinel-личность.
    expect(sentinelMarkerPresent()).toBe(false);
  });
});
