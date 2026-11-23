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
 * LABGUARD-FE-002 (audit 3886, round 13) — fail-first.
 *
 * guardedNavigate резолвил строковые цели против origin-корня:
 * new URL('?tab=templates', window.location.origin).pathname === '/' —
 * query-only/fragment-навигация С /lab misклассифицировалась как уход
 * из лаборатории: при dirty открывался destructive Save/Discard/Cancel
 * диалог (Discard мог сбросить черновик) для внутрилабораторного
 * переключения вкладки. Резолв обязан идти против ТЕКУЩЕГО href — как
 * в resolveToHref и в семантике React Router. Падает на до-фиксном коде.
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

function LabNavPage() {
  const navigate = useGuardedLabNavigate();
  const location = useLocation();
  const currentPath = location.pathname + location.search;
  return (
    <div>
      <button type="button" onClick={() => navigate('?tab=templates')}>query-only</button>
      <button type="button" onClick={() => navigate('#results')}>fragment-only</button>
      <button type="button" onClick={() => navigate(currentPath)}>same-href</button>
      <button type="button" onClick={() => navigate('/profile')}>leave</button>
    </div>
  );
}

function RegistrationBridge({
  registration,
  sourceDiscard,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
  sourceDiscard?: () => void;
}) {
  const guard = useLabDirtyGuard();
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
  window.history.replaceState(null, '', '/lab');
  return render(
    <ThemeProvider>
      <BrowserRouter>
        <LabDirtyGuardProvider>
          <RegistrationBridge registration={registration} sourceDiscard={sourceDiscard} />
          <LocationProbe />
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

async function settle() {
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
}

describe('LABGUARD-FE-002: query-only and fragment navigation stays in-lab', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('a DIRTY query-only navigation switches the tab WITHOUT a destructive dialog', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration });
    await registerDirtySource(registration);
    expect(sentinelMarkerPresent()).toBe(true);
    const armedLength = window.history.length;

    // До фикса: targetPathname резолвился в '/' → guardRouteLeave →
    // destructive диалог, URL оставался /lab, вкладка не переключалась.
    fireEvent.click(screen.getByRole('button', { name: 'query-only' }));
    await settle();

    expect(screen.getByTestId('location')).toHaveTextContent('/lab?tab=templates');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(window.history.length).toBe(armedLength);
    expect(sentinelMarkerPresent()).toBe(true);
  });

  it('a DIRTY fragment-only navigation also stays in-lab without a dialog', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration });
    await registerDirtySource(registration);

    fireEvent.click(screen.getByRole('button', { name: 'query-only' }));
    await settle();
    fireEvent.click(screen.getByRole('button', { name: 'fragment-only' }));
    await settle();

    // Fragment-only To не покидает лабораторный маршрут (React Router
    // сбрасывает search при hash-only строке — pathname остаётся /lab),
    // диалога нет, история не растёт, sentinel жив.
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect(screen.getByTestId('location')).not.toHaveTextContent('/profile');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(sentinelMarkerPresent()).toBe(true);
  });

  it('the same href remains a full no-op (in-lab identity)', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration });
    await registerDirtySource(registration);

    fireEvent.click(screen.getByRole('button', { name: 'query-only' }));
    await settle();
    const lengthBefore = window.history.length;

    fireEvent.click(screen.getByRole('button', { name: 'same-href' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab?tab=templates');
    expect(window.history.length).toBe(lengthBefore);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('a REAL leave (/profile) still opens the guard dialog — the check is not weakened', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    const discard = vi.fn();
    renderLabApp({ registration, sourceDiscard: discard });
    await registerDirtySource(registration);

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
    expect(discard).toHaveBeenCalledTimes(1);
  });
});
