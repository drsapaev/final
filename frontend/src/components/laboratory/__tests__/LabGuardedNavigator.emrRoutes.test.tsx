import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  LabDirtyGuardProvider,
  useGuardedLabNavigate,
  useLabDirtyGuard,
} from '../LabDirtyGuardContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * RETRO-3971-04 residual (post-merge re-review of #4009, PR #4000 ledger):
 * the EMR container lives on the doctor routes (/doctor/dermatology,
 * /doctor/cardiology). #4009 added the last-chance unmount flush, but the
 * fire-and-forget effect destructor cannot keep a clinical draft alive:
 * browser Back / SPA navigation unmount the panel before the POST resolves.
 *
 * The App-level dirty guard (PR 3351) already owns a shared source registry
 * and a route-leave sentinel — but the sentinel only arms on the LabPanel
 * route, so a doctor route with a dirty EMR draft loses the draft on
 * browser Back with NO dialog. These tests pin the residual acceptance:
 *   - browser Back on a doctor route with a dirty EMR draft must open the
 *     shared guard dialog and keep the panel mounted (URL unchanged);
 *   - the confirmed Back leave lands on the real previous route;
 *   - a SPA leave through the guarded navigator from a doctor route with a
 *     dirty EMR draft opens the same dialog (this part already worked — it
 *     is pinned here as a regression guard for the residual contract);
 *   - the shell navigation points (Command Palette) and the EMR container
 *     wiring (useEMRLeaveGuard) must route through the same machinery.
 */

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function readSource(relativePath: string): string {
  return fs.readFileSync(path.join(__dirname, relativePath), 'utf8');
}

const SENTINEL_STATE_KEY = '__labLeaveGuardSentinel';

function sentinelMarkerPresent(): boolean {
  return Boolean(
    (window.history.state as Record<string, unknown> | null)?.[SENTINEL_STATE_KEY],
  );
}

/** Постоянный (вне Routes) индикатор текущего пути. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
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

function DermPage() {
  const navigate = useGuardedLabNavigate();
  return (
    <div>
      dermatology panel page
      <button type="button" onClick={() => navigate('/profile')}>leave</button>
    </div>
  );
}

/** Держит ссылку на регистрацию EMR-источника для act-вызова после монтирования. */
function RegistrationBridge({
  registration,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
}) {
  const guard = useLabDirtyGuard();
  // Рендер-присваивание: тест читает registration.current после render().
  registration.current = (source) => guard.registerDirtySource(source);
  return null;
}

function renderEmrRouteApp({
  registration,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
}) {
  // Предшественник /profile + SPA-переход на doctor-маршрут (router idx).
  window.history.replaceState(null, '', '/profile');
  const utils = render(
    <ThemeProvider>
      <BrowserRouter>
        <LabDirtyGuardProvider>
          <RegistrationBridge registration={registration} />
          <LocationProbe />
          <Routes>
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/doctor/dermatology" element={<DermPage />} />
          </Routes>
        </LabDirtyGuardProvider>
      </BrowserRouter>
    </ThemeProvider>,
  );
  // Регистрируем мост до навигации, чтобы источник был доступен на derm-странице.
  return utils;
}

async function registerEmrDraftSource(
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] },
) {
  await act(async () => {
    registration.current?.({
      id: 'emr-visit-42',
      isDirty: () => true,
      save: vi.fn().mockResolvedValue(undefined),
      discard: vi.fn(),
    });
  });
}

async function settleRouter() {
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
    // jsdom History.go/back выполняет traversal ЗАДАЧОЙ (макротаска):
    // микротасок недостаточно для приземления POP-рендера роутера.
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe('Route-level leave guard on EMR doctor routes (RETRO-3971-04 residual)', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('browser Back on a doctor route with a dirty EMR draft opens the guard dialog and keeps the panel URL', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderEmrRouteApp({ registration });

    // SPA-переход profile → doctor route (clean registry: сразу выполняется).
    fireEvent.click(screen.getByRole('button', { name: 'to-derm' }));
    await settleRouter();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(screen.getByText('dermatology panel page')).toBeInTheDocument();

    // Dirty EMR draft регистрируется общим реестром (панель = visit owner).
    await registerEmrDraftSource(registration);
    // ARM: sentinel должен быть вооружён на doctor-маршруте (не только /lab).
    expect(sentinelMarkerPresent()).toBe(true);

    const urlBeforeBack = window.location.pathname;

    // Browser Back: панель обязана остаться смонтированной (twin-запись), а
    // не молча размонтироваться с потерей клинического черновика.
    window.history.back();
    await settleRouter();

    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(window.location.pathname).toBe(urlBeforeBack);
    expect(screen.getByText('dermatology panel page')).toBeInTheDocument();
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeInTheDocument();

    // Отмена: пользователь и черновик остаются на месте.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await settleRouter();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(screen.getByText('dermatology panel page')).toBeInTheDocument();
  });

  it('a confirmed browser-Back leave lands on the previous route', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderEmrRouteApp({ registration });

    fireEvent.click(screen.getByRole('button', { name: 'to-derm' }));
    await settleRouter();

    await registerEmrDraftSource(registration);

    window.history.back();
    await settleRouter();

    const dialog = await screen.findByRole('dialog');
    // Discard — осознанный уход: черновик сброшен, переход выполняется.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await settleRouter();

    expect(screen.getByTestId('location')).toHaveTextContent('/profile');
    expect(screen.getByText('profile page')).toBeInTheDocument();
  });

  it('a SPA leave from a doctor route with a dirty EMR draft opens the shared guard dialog (regression pin)', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderEmrRouteApp({ registration });

    fireEvent.click(screen.getByRole('button', { name: 'to-derm' }));
    await settleRouter();

    await registerEmrDraftSource(registration);

    fireEvent.click(screen.getByRole('button', { name: 'leave' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(screen.getByText('dermatology panel page')).toBeInTheDocument();

    // Отмена — Stay: ни перехода, ни потери черновика.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await settleRouter();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('CommandPalette shell navigations route through the guarded navigator (App passes the guarded navigate prop)', () => {
    // CommandPalette получает navigate через prop; App передаёт вариант из
    // useGuardedLabNavigate — переходы из Command Palette проходят через тот же
    // общий реестр dirty-источников (regression pin для residual-контракта).
    const appSource = readSource('../../../App.tsx');
    expect(appSource).toContain('const navigate = useGuardedLabNavigate();');
    expect(appSource).toMatch(/<CommandPalette[^>]*navigate=\{navigate\}/);
  });

  it('EMRContainerV2 wires its dirty draft into the shared route-level leave guard', () => {
    const source = readSource('../../../components/emr-v2/EMRContainerV2.tsx');
    expect(source).toContain('useEMRLeaveGuard(');
  });
});
