import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  LabDirtyGuardProvider,
  useLabDirtyGuard,
} from '../LabDirtyGuardContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * LABGUARD-FE-003 (audit 3886, round 13) — fail-first.
 *
 * Второй dirty-guardTransition во время ОТКРЫТОГО диалога молча
 * перезаписывал pendingTransitionRef: первый интент (Logout: onLeave
 * чистит токен и уводит на /login) подменялся вторым browser-Back
 * коллбеком (navigate(-2)) — тот же модальный экран выполнял уже
 * ЧУЖОЙ переход. Диалог обязан быть иммутабельным, пока открыт: новый
 * интент отклоняется (false), подтверждение выполняет ПЕРВЫЙ интент.
 * Падает на до-фиксном коде: Save/Discard уходят по второму интенту.
 */

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

function ShellPage() {
  const navigate = useNavigate();
  const { guardRouteLeave } = useLabDirtyGuard();
  return (
    <div>
      shell page
      <button
        type="button"
        onClick={() => {
          guardRouteLeave(() => { navigate('/login'); });
        }}
      >
        logout-intent
      </button>
      <button
        type="button"
        onClick={() => {
          guardRouteLeave(() => { navigate('/health'); });
        }}
      >
        back-intent
      </button>
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
  window.history.replaceState(null, '', '/lab');
  return render(
    <ThemeProvider>
      <BrowserRouter>
        <LabDirtyGuardProvider>
          <RegistrationBridge registration={registration} />
          <LocationProbe />
          <Routes>
            <Route path="/lab" element={<ShellPage />} />
            <Route path="/login" element={<div>login page</div>} />
            <Route path="/health" element={<div>health page</div>} />
          </Routes>
        </LabDirtyGuardProvider>
      </BrowserRouter>
    </ThemeProvider>,
  );
}

async function registerDirtySource(
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

async function settle() {
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
}

describe('LABGUARD-FE-003: an open dialog keeps the FIRST leave intent', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('a second intent during the open dialog does not replace the first (Save path)', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration });
    const save = vi.fn().mockResolvedValue(undefined);
    const discard = vi.fn();
    await registerDirtySource(registration, { save, discard });

    // Первый интент — Logout: подтверждённый уход уводит на /login.
    fireEvent.click(screen.getByRole('button', { name: 'logout-intent' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    // Второй интент (второй browser-Back при открытом диалоге) прибывает
    // ДО решения пользователя. До фикса он молча подменял первый.
    fireEvent.click(screen.getByRole('button', { name: 'back-intent' }));
    await settle();
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Подтверждение Save выполняет ПЕРВЫЙ интент (login), не второй.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить и перейти' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/login');
    expect(save).toHaveBeenCalledTimes(1);
  });

  it('a second intent during the open dialog does not replace the first (Discard path)', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration });
    const save = vi.fn().mockResolvedValue(undefined);
    const discard = vi.fn();
    await registerDirtySource(registration, { save, discard });

    fireEvent.click(screen.getByRole('button', { name: 'logout-intent' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(screen.getByRole('button', { name: 'back-intent' }));
    await settle();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/login');
    expect(discard).toHaveBeenCalledTimes(1);
  });

  it('Cancel keeps everything in place; a NEW intent works only after the dialog closes', async () => {
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    renderLabApp({ registration });
    const save = vi.fn().mockResolvedValue(undefined);
    const discard = vi.fn();
    await registerDirtySource(registration, { save, discard });

    fireEvent.click(screen.getByRole('button', { name: 'logout-intent' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(screen.getByRole('button', { name: 'back-intent' }));
    await settle();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await settle();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');
    expect(save).not.toHaveBeenCalled();
    expect(discard).not.toHaveBeenCalled();

    // Диалог закрыт — новый интент снова может спросить пользователя.
    fireEvent.click(screen.getByRole('button', { name: 'back-intent' }));
    const dialog2 = await screen.findByRole('dialog');
    fireEvent.click(within(dialog2).getByRole('button', { name: 'Выйти без сохранения' }));
    await settle();
    expect(screen.getByTestId('location')).toHaveTextContent('/health');
    expect(discard).toHaveBeenCalledTimes(1);
  });
});
