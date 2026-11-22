/**
 * CSH-FE-050 (follow-up audit 2026-11-02): сумма заявки на возврат в
 * таблице кассира обязана читаться из РЕАЛЬНОГО поля ответа.
 *
 * Дефект: backend `RefundRequestResponse` (force_majeure.py) отдаёт
 * `refund_amount` ( сериализатор force_majeure_api_service тоже пишет
 * `refund_amount`), а таблица читала колонку `amount` — поля в ответе нет,
 * `formatRefundAmount(undefined)` рендерил «—» для каждой легитимной суммы
 * возврата рядом с кнопками approve/reject/complete.
 *
 * Red-first: монтируем реальную RefundRequestsTable на СИНТЕТИЧЕСКОМ
 * ответе, совпадающем с DTO бэкенда (refund_amount, БЕЗ amount), и
 * требуем видимую сумму. Проверяем и zero/missing-кейсы, и что легаси-поле
 * `amount` само по себе сумму НЕ рисует (читается только контрактное поле).
 *
 * Примечание техники: formatUZS использует NBSP-разделитель тысяч
 * (ru-RU), который testing-library getByText не матчит exact-строкой —
 * поэтому суммы ассертуются прямым сравнением textContent ячейки
 * (конвенция CashierStatsCard.test.tsx).
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

const notifyMocks = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: apiMocks.get,
    post: apiMocks.post,
  },
}));

vi.mock('../../../services/notify', () => ({
  default: notifyMocks,
}));

import RefundRequestsTable from '../RefundRequestsTable';
import { formatUZS } from '../../../utils/formatCurrency';

// Точная форма строки ответа backend: refund_amount, amount ОТСУТСТВУЕТ.
const backendRefundDto = (overrides: Record<string, unknown> = {}) => ({
  id: 77,
  patient_id: 12,
  patient_name: 'Тестов Тест Тестович',
  payment_id: 900,
  original_amount: 100000,
  refund_amount: 70000,
  commission_amount: 0,
  refund_type: 'bank_transfer',
  status: 'pending',
  reason: 'Отмена услуги по инициативе клиники',
  is_automatic: false,
  bank_card_number: null,
  created_at: '2026-11-04T09:15:00Z',
  processed_at: null,
  processed_by_name: null,
  available_actions: ['approve', 'reject'],
  can_approve: true,
  can_reject: true,
  can_complete: false,
  ...overrides,
});

const renderTable = () => render(<RefundRequestsTable />);

const amountCellTexts = () =>
  Array.from(document.querySelectorAll('.refund-cell-amount')).map(
    (el) => el.textContent ?? '',
  );

describe('RefundRequestsTable amount column (CSH-FE-050)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.get.mockResolvedValue({ data: [] });
  });

  it('renders the refund_amount from the actual backend DTO (70 000, not «—»)', async () => {
    apiMocks.get.mockResolvedValue({ data: [backendRefundDto()] });

    renderTable();

    await waitFor(() => {
      expect(screen.getByText('Тестов Тест Тестович')).toBeInTheDocument();
    });
    expect(amountCellTexts()).toEqual([formatUZS(70000)]);
  });

  it('shows «—» for a row where refund_amount is missing (honest placeholder)', async () => {
    apiMocks.get.mockResolvedValue({
      data: [backendRefundDto({ refund_amount: undefined })],
    });

    renderTable();

    await waitFor(() => {
      expect(screen.getByText('Тестов Тест Тестович')).toBeInTheDocument();
    });
    expect(amountCellTexts()).toEqual(['—']);
  });

  it('does NOT read the nonexistent legacy `amount` field', async () => {
    // Демонстрация контракта: строка ТОЛЬКО со старым полем amount не
    // показывает сумму — колонка обязана читать refund_amount, а не
    // выдумывать её из соседнего поля.
    apiMocks.get.mockResolvedValue({
      data: [backendRefundDto({ refund_amount: undefined, amount: 55000 })],
    });

    renderTable();

    await waitFor(() => {
      expect(screen.getByText('Тестов Тест Тестович')).toBeInTheDocument();
    });
    expect(amountCellTexts()).toEqual(['—']);
    expect(amountCellTexts()).not.toContain(formatUZS(55000));
  });

  it('renders refund_amount as string sum as well (serializer may emit strings)', async () => {
    apiMocks.get.mockResolvedValue({
      data: [backendRefundDto({ refund_amount: '125000' })],
    });

    renderTable();

    await waitFor(() => {
      expect(screen.getByText('Тестов Тест Тестович')).toBeInTheDocument();
    });
    expect(amountCellTexts()).toEqual([formatUZS('125000')]);
  });

  it('keeps several rows distinct: each refund_amount renders in its own row', async () => {
    apiMocks.get.mockResolvedValue({
      data: [
        backendRefundDto({ id: 1, patient_name: 'Пациент Первый', refund_amount: 30000 }),
        backendRefundDto({ id: 2, patient_name: 'Пациент Второй', refund_amount: 45000 }),
      ],
    });

    renderTable();

    await waitFor(() => {
      expect(screen.getByText('Пациент Первый')).toBeInTheDocument();
      expect(screen.getByText('Пациент Второй')).toBeInTheDocument();
    });
    expect(amountCellTexts()).toEqual([formatUZS(30000), formatUZS(45000)]);
  });
});
