import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// RQ-10 (S-08): частичный результат QR-регистрации — успешные талоны видны
// отдельно от неудачных направлений; нет общего вводящего в заблуждение
// успеха; потеря ответа после успешного серверного сохранения не маскируется
// сообщением «сессия не найдена» без честного пути обращения.
//
// Контракт backend: complete_join_session_multiple →
//   { success: len(entries) > 0, entries: [...], errors: [...] | None }.
// 0/2 до фронта не доходит как 200 (backend rollback + ValueError).

const queueApiMocks = vi.hoisted(() => ({
  fetchQrTokenInfo: vi.fn(),
  startQueueJoinSession: vi.fn(),
  completeQueueJoinSession: vi.fn(),
}));

vi.mock('../../api/queue', () => queueApiMocks);

import QueueJoin from '../QueueJoin';

const TWO_SPECIALISTS = [
  { id: 6, specialty: 'cardio', specialty_display: 'Кардиолог', icon: '❤️', color: '#FF3B30' },
  {
    id: 9,
    specialty: 'lab',
    specialty_display: 'Лаборант',
    full_name: 'Тестов Тест Тестович',
    icon: '🧪',
    color: '#007AFF',
  },
];

function setupQueueApiMock() {
  queueApiMocks.fetchQrTokenInfo.mockResolvedValue({
    queue_active: true,
    allowed: true,
    status: 'available',
    message: 'Запись доступна',
    queue_length: 2,
    department_name: 'Кардиология',
    specialist_name: 'Кардиолог',
    target_date: '2026-02-21',
    selectable_specialists: TWO_SPECIALISTS,
  });
  queueApiMocks.startQueueJoinSession.mockResolvedValue({
    session_token: 'session-token',
    queue_info: {
      is_clinic_wide: true,
      queue_active: true,
      allowed: true,
      status: 'available',
      message: 'Запись доступна',
      queue_length: 2,
      department_name: 'Кардиология',
      specialist_name: 'Кардиолог',
      target_date: '2026-02-21',
      selectable_specialists: TWO_SPECIALISTS,
    },
  });
}

function renderQueueJoin(token = 'test-token') {
  return render(
    <MemoryRouter initialEntries={[`/queue/join/${token}`]}>
      <Routes>
        <Route path="/queue/join/:token" element={<QueueJoin />} />
      </Routes>
    </MemoryRouter>
  );
}

async function submitClinicWideJoin() {
  fireEvent.click(await screen.findByLabelText(/кардиолог/i));
  fireEvent.click(screen.getByLabelText(/лаборант/i));
  fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));

  fireEvent.change(await screen.findByLabelText(/фио/i), {
    target: { value: 'Тест Пациент' },
  });
  fireEvent.change(screen.getByLabelText(/номер телефона/i), {
    target: { value: '+998 (90) 123-45-67' },
  });
  // act: обработчик async — флашим всю цепочку (reject + state-обновления),
  // иначе DOM ассертится в транзиентном состоянии (act-предупреждения).
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Присоединиться/i }));
  });
}

const makeHttpError = (status: number, detail: string) =>
  Object.assign(new Error('Request failed with status code ' + status), {
    response: { status, data: { detail } },
  });

const NETWORK_ERROR = Object.assign(new Error('Network Error'), { response: undefined });

describe('QueueJoin partial result (RQ-10, S-08)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupQueueApiMock();

    const storage = new Map();
    window.localStorage.getItem = vi.fn((key) => (storage.has(key) ? storage.get(key) : null));
    window.localStorage.setItem = vi.fn((key, value) => {
      storage.set(key, String(value));
    });
    window.localStorage.removeItem = vi.fn((key) => {
      storage.delete(key);
    });
    window.localStorage.clear = vi.fn(() => {
      storage.clear();
    });
  });

  it('2/2: показывает оба талона и не показывает блок неудачных направлений', async () => {
    queueApiMocks.completeQueueJoinSession.mockResolvedValue({
      success: true,
      queue_time: '2026-02-21T09:00:00Z',
      entries: [
        { specialist_id: 6, queue_number: 3, specialist_name: 'Кардиолог', department: 'cardiology' },
        { specialist_id: 9, queue_number: 5, specialist_name: 'Лаборант', department: 'lab' },
      ],
      errors: null,
      message: 'Создано 2 записей, ошибок: 0',
    });

    renderQueueJoin('partial-all-ok');
    await submitClinicWideJoin();

    expect(await screen.findByText(/Вы зарегистрированы в очередях!/i)).toBeInTheDocument();
    expect(screen.getByText(/№3/)).toBeInTheDocument();
    expect(screen.getByText(/№5/)).toBeInTheDocument();
    expect(screen.queryByText(/Не удалось записать/i)).not.toBeInTheDocument();
  });

  it('1/2: успешный талон виден отдельно, неудачное направление — с причиной, без вводящего в заблуждение общего успеха', async () => {
    queueApiMocks.completeQueueJoinSession.mockResolvedValue({
      success: true,
      queue_time: '2026-02-21T09:00:00Z',
      entries: [
        { specialist_id: 6, queue_number: 3, specialist_name: 'Кардиолог', department: 'cardiology' },
      ],
      errors: [{ specialist_id: 9, error: 'Очередь достигла лимита' }],
      message: 'Создано 1 записей, ошибок: 1',
    });

    renderQueueJoin('partial-one-of-two');
    await submitClinicWideJoin();

    // Успешный талон виден со своим номером (из entries, а не пустой top-level queue_number).
    expect(await screen.findByText(/№3/)).toBeInTheDocument();
    // Заголовок не утверждает общий успех.
    expect(screen.getByText(/частично/i)).toBeInTheDocument();
    // Неудачное направление показано отдельно с причиной и понятным названием.
    expect(screen.getByText(/Не удалось записать/i)).toBeInTheDocument();
    expect(screen.getByText(/Тестов Тест Тестович/i)).toBeInTheDocument();
    expect(screen.getByText(/Очередь достигла лимита/i)).toBeInTheDocument();
  });

  it('0/2: серверная ошибка не называется успехом — виден баннер с причиной', async () => {
    queueApiMocks.completeQueueJoinSession.mockRejectedValue(
      makeHttpError(400, 'Очередь достигла лимита')
    );

    renderQueueJoin('partial-zero-of-two');
    await submitClinicWideJoin();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Очередь достигла лимита/i);
    expect(screen.queryByText(/Вы в очереди!/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Вы зарегистрированы в очередях!/i)).not.toBeInTheDocument();
  });

  it('потеря ответа после успешного сохранения: повтор дает честный совет вместо вводящего «сессия не найдена»', async () => {
    queueApiMocks.completeQueueJoinSession
      .mockRejectedValueOnce(NETWORK_ERROR)
      .mockRejectedValueOnce(makeHttpError(400, 'Сессия не найдена или истекла'));

    renderQueueJoin('partial-lost-response');
    await submitClinicWideJoin();

    // Первая попытка: ответ потерян — результат неизвестен, это сказано честно.
    const firstAlert = await screen.findByRole('alert');
    expect(firstAlert).toHaveTextContent(/результат отправки неизвестен/i);

    // Повтор той же сессией: НЕ стартует новая сессия (новый session_token не создается).
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Присоединиться/i }));
    });

    const secondAlert = await screen.findByRole('alert');
    expect(secondAlert).toHaveTextContent(/Сессия не найдена или истекла/i);
    // Честный путь обращения: запись могла быть создана первой попыткой.
    expect(screen.getByText(/была создана при предыдущей попытке/i)).toBeInTheDocument();

    // Сессия одна: повтор идет тем же session_token, без пересоздания сессии.
    expect(queueApiMocks.startQueueJoinSession).toHaveBeenCalledTimes(1);
    expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(2);
    const firstCall = queueApiMocks.completeQueueJoinSession.mock.calls[0][0] as Record<string, unknown>;
    const secondCall = queueApiMocks.completeQueueJoinSession.mock.calls[1][0] as Record<string, unknown>;
    expect(secondCall.session_token).toBe(firstCall.session_token);
  });
});
