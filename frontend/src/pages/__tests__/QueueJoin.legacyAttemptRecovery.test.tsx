/**
 * QR-FE-005/006 (follow-up audit 2026-11-02): восстановление исходной
 * попытки legacy QR-токена и устойчивость к сбою хранилища.
 *
 * 005: после потери ответа /join/complete повторный вход по тому же QR
 *      токену БЕЗусловно чеканил НОВУЮ сессию (startJoinSession поверх
 *      сохранённой) — исходная идентичность попытки терялась навсегда.
 *      Теперь: non-PHI envelope (пространство имён 'qr') сохраняет
 *      оригинальный session-токен; boot с UNKNOWN-исходом НЕ стартует
 *      новую сессию, а ведёт в панель сверки; «Проверить» завершает
 *      ИСХОДНУЮ сессию; успех снимает envelope.
 * 006: сбой localStorage (квота/безопасный режим) в том же try, что и
 *      успешный startQueueJoinSession, превращал живую серверную сессию
 *      в «экран ошибки». Теперь персистенция токена — best-effort.
 *
 * Red-first: на префиксном коде boot звал startQueueJoinSession снова
 * (новый токен) и панели сверки не было; падение setItem валило boot в
 * error-шаг.
 */
import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const queueApiMocks = vi.hoisted(() => ({
  fetchQrTokenInfo: vi.fn(),
  startQueueJoinSession: vi.fn(),
  completeQueueJoinSession: vi.fn(),
  probeQueueJoinSession: vi.fn(),
}));

vi.mock('../../api/queue', () => queueApiMocks);

import QueueJoin from '../QueueJoin';

const TOKEN = 'legacy-qr-token';
const ORIGINAL_SESSION = 'original-session-token';

const TWO_SPECIALISTS = [
  { id: 6, specialty: 'cardio', specialty_display: 'Кардиолог', icon: '❤️', color: '#FF3B30' },
  { id: 9, specialty: 'lab', specialty_display: 'Лаборант', icon: '🧪', color: '#007AFF' },
];

function seedUnknownEnvelope(token: string, sessionToken: string) {
  window.localStorage.setItem(
    `queue_join_attempt_qr_${token}__${sessionToken}`,
    JSON.stringify({
      ts: Date.now(),
      publicCode: token,
      sessionToken,
      profileId: null,
      directionTitle: null,
      completeAttempted: true,
      outcomeUnknown: true,
      attemptExpiresAt: null,
    }),
  );
}

function renderQueueJoin(token = TOKEN) {
  return render(
    <MemoryRouter initialEntries={[`/queue/join/${token}`]}>
      <Routes>
        <Route path="/queue/join/:token" element={<QueueJoin />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  queueApiMocks.fetchQrTokenInfo.mockReset();
  queueApiMocks.startQueueJoinSession.mockReset();
  queueApiMocks.completeQueueJoinSession.mockReset();
  queueApiMocks.probeQueueJoinSession.mockReset();

  queueApiMocks.fetchQrTokenInfo.mockResolvedValue({
    queue_active: true,
    allowed: true,
    status: 'available',
    message: 'Запись доступна',
    queue_length: 2,
    department_name: 'Кардиология',
    specialist_name: 'Кардиолог',
    target_date: '2026-11-05',
    is_clinic_wide: true,
    selectable_specialists: TWO_SPECIALISTS,
  });
  queueApiMocks.startQueueJoinSession.mockResolvedValue({
    session_token: 'fresh-session-token',
    queue_info: { is_clinic_wide: true, selectable_specialists: TWO_SPECIALISTS },
  });
});

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe('QR-FE-005: legacy UNKNOWN attempt keeps its original identity', () => {
  it('boot does NOT mint a new session and shows the reconcile panel', async () => {
    seedUnknownEnvelope(TOKEN, ORIGINAL_SESSION);
    window.localStorage.setItem(`queue_session_${TOKEN}`, ORIGINAL_SESSION);

    renderQueueJoin();

    // Специалисты загружены из token-info — UI живёт.
    expect(await screen.findByLabelText(/кардиолог/i)).toBeInTheDocument();

    // ГЛАВНОЕ: новая сессия НЕ отчеканена — оригинальная идентичность
    // попытки сохранена для сверки.
    await act(async () => {
      await Promise.resolve();
    });
    expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
    expect(queueApiMocks.fetchQrTokenInfo).toHaveBeenCalledTimes(1);
  });

  it('«Проверить» completes the ORIGINAL session, success clears the envelope', async () => {
    seedUnknownEnvelope(TOKEN, ORIGINAL_SESSION);
    window.localStorage.setItem(`queue_session_${TOKEN}`, ORIGINAL_SESSION);

    renderQueueJoin();
    expect(await screen.findByLabelText(/кардиолог/i)).toBeInTheDocument();

    // Общий QR: выбор врача → форма → панель сверки.
    fireEvent.click(screen.getByLabelText(/кардиолог/i));
    fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));

    const nameInput = await screen.findByLabelText(/фио/i);
    fireEvent.change(nameInput, { target: { value: 'Тестов Тест Тестович' } });
    const phoneInput = screen.getByLabelText(/номер телефона/i);
    fireEvent.change(phoneInput, { target: { value: '998901234567' } });

    expect(await screen.findByTestId('qj-reconcile-banner')).toBeInTheDocument();

    queueApiMocks.completeQueueJoinSession.mockResolvedValueOnce({
      success: true,
      queue_number: 7,
      queue_length: 3,
      estimated_wait_time: 15,
      specialist_name: 'Кардиолог',
      department: 'Кардиология',
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId('qj-reconcile-check'));
    });

    // Завершена ИСХОДНАЯ сессия — не свежая.
    expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
    expect(queueApiMocks.completeQueueJoinSession.mock.calls[0][0]).toMatchObject({
      session_token: ORIGINAL_SESSION,
      patient_name: 'Тестов Тест Тестович',
      phone: '998901234567',
    });

    // Успех: talon показан, envelope снят.
    expect(await screen.findByText(/7/)).toBeInTheDocument();
    expect(
      window.localStorage.getItem(`queue_join_attempt_qr_${TOKEN}__${ORIGINAL_SESSION}`),
    ).toBeNull();
  });

  it('a plain submit is gated while the reconcile panel is active', async () => {
    seedUnknownEnvelope(TOKEN, ORIGINAL_SESSION);
    window.localStorage.setItem(`queue_session_${TOKEN}`, ORIGINAL_SESSION);

    renderQueueJoin();
    expect(await screen.findByLabelText(/кардиолог/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/кардиолог/i));
    fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));

    const nameInput = await screen.findByLabelText(/фио/i);
    fireEvent.change(nameInput, { target: { value: 'Тестов Тест Тестович' } });
    fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '998901234567' } });

    // Обычный сабмит (Enter) заблокирован панелью — complete не уходит.
    await act(async () => {
      fireEvent.submit(nameInput.closest('form') ?? nameInput);
    });
    expect(queueApiMocks.completeQueueJoinSession).not.toHaveBeenCalled();
  });
});

describe('QR-FE-006: a broken store must not kill the boot', () => {
  it('quota-exceeded setItem keeps the backend-started session alive', async () => {
    // Инстанс-переопределение (spy на Storage.prototype в jsdom не
    // перехватывает вызовы window.localStorage): setItem ВСЕГДА падает.
    const realSetItem = window.localStorage.setItem.bind(window.localStorage);
    let threw = 0;
    Object.defineProperty(window.localStorage, 'setItem', {
      configurable: true,
      value: () => {
        threw += 1;
        throw new DOMException('quota exceeded', 'QuotaExceededError');
      },
    });

    try {
      renderQueueJoin();

      // Бэкенд-старт прошёл, экран дошёл до выбора специалистов — НЕ error.
      expect(await screen.findByLabelText(/кардиолог/i)).toBeInTheDocument();
      expect(queueApiMocks.startQueueJoinSession).toHaveBeenCalledTimes(1);
      // Сбой хранилища РЕАЛЬНО происходил (не вакуумный прогон).
      expect(threw).toBeGreaterThan(0);
    } finally {
      Object.defineProperty(window.localStorage, 'setItem', {
        configurable: true,
        value: realSetItem,
      });
    }
  });
});
