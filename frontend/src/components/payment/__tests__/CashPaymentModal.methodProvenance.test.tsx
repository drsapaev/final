/**
 * CSH-FE-039 (follow-up audit 2026-11-02) — провенанс метода в модалке
 * прямой кассовой оплаты.
 *
 * Дефект: CashPaymentModal предлагала click/payme, но отправляла их в
 * тот же прямой кассовой эндпоинт, который немедленно ставит
 * status='paid' без подтверждения провайдером. Кассир мог «провести»
 * Click/PayMe одним кликом без доказательства списания.
 *
 * Фикс (frontend-половина; backend валидирует DTO в
 * cashier/_helpers.py): в модалке остаются ТОЛЬКО методы с ручным
 * документальным подтверждением кассира — cash и card. Провайдерские
 * методы инициируются отдельным онлайн-виджетом (pending → webhook → paid).
 *
 * Техника: macos Select — кастомный listbox (role="option" рендерится в
 * portal только при открытии), поэтому тест открывает dropdown кликом по
 * триггеру и читает метки опций (t-мок возвращает ключи 1:1 значениям).
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params && params.amount !== undefined ? `${key}:${String(params.amount)}` : key,
  }),
}));

vi.mock('../../../services/notify', () => ({
  default: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

import CashPaymentModal from '../CashPaymentModal';

const visit = {
  id: 42,
  patient_id: 7,
  patient_name: 'Тестов Тест Тестович',
  department: 'Терапия',
  appointment_date: '2026-11-02',
  appointment_time: '10:00',
  total_amount: '100000',
  paid_amount: '0',
  remaining_amount: '100000',
};

const openModal = () =>
  render(<CashPaymentModal appointment={visit} onProcessPayment={vi.fn()} onClose={vi.fn()} />);

const openMethodDropdown = () => {
  fireEvent.click(screen.getByLabelText('payment.pay_cash_method_aria'));
  return screen.getAllByRole('option').map((o) => o.textContent);
};

describe('CashPaymentModal — CSH-FE-039 method provenance', () => {
  it('offers only manually receipted methods: cash and card', () => {
    openModal();

    expect(openMethodDropdown()).toEqual([
      'payment.pay_cash_method_cash',
      'payment.pay_cash_method_card',
    ]);
  });

  it('never offers hosted provider methods (click/payme) in the immediate-paid modal', () => {
    openModal();
    openMethodDropdown();

    const optionLabels = screen
      .getAllByRole('option')
      .map((o) => o.textContent);
    expect(optionLabels).not.toContain('payment.pay_cash_method_click');
    expect(optionLabels).not.toContain('payment.pay_cash_method_payme');
  });

  it('defaults to cash (trigger shows the cash label before opening)', () => {
    openModal();

    const trigger = screen.getByLabelText('payment.pay_cash_method_aria');
    expect(trigger.textContent).toContain('payment.pay_cash_method_cash');
  });

  it('modal renders for a grouped (multi-visit) row with the same method set', () => {
    render(
      <CashPaymentModal
        appointment={{ ...visit, visit_ids: [1, 2], isBackendGrouped: true }}
        onProcessPayment={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText('payment.pay_cash_title')).toBeInTheDocument();
    expect(openMethodDropdown()).toEqual([
      'payment.pay_cash_method_cash',
      'payment.pay_cash_method_card',
    ]);
  });
});
