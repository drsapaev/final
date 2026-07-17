// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FinanceModal from '../FinanceModal.tsx';
import { ThemeProvider } from '../../../contexts/ThemeContext.tsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.tsx';

const renderFinanceModal = (props = {}) => render(
  <MacOSThemeProvider>
    <ThemeProvider>
      <FinanceModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        loading={false}
        patients={[]}
        doctors={[]}
        {...props}
      />
    </ThemeProvider>
  </MacOSThemeProvider>
);

describe('FinanceModal', () => {
  beforeEach(() => {
    localStorage.clear();

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn()
      }))
    });
  });

  it('shows an integer UZS amount hint and no longer enforces a 1000-step browser constraint', () => {
    renderFinanceModal();

    const amountInput = screen.getByPlaceholderText('100000');

    expect(amountInput).toHaveAttribute('min', '1');
    expect(amountInput).toHaveAttribute('step', '1');
    expect(amountInput).toHaveAttribute('inputmode', 'numeric');
    expect(screen.getByText('Введите сумму целым числом в UZS. Например: 12500.')).toBeInTheDocument();
  });

  it('does not initialize an existing transaction with missing status as completed', () => {
    renderFinanceModal({
      transaction: {
        id: 601,
        type: 'income',
        category: 'РљРѕРЅСЃСѓР»СЊС‚Р°С†РёСЏ',
        amount: 90000,
        description: 'Backend row without status',
        paymentMethod: 'cash',
        transactionDate: '2026-03-27',
      },
    });

    const statusSelect = screen.getByRole('button', { name: 'Статус не передан' });

    expect(statusSelect).toHaveTextContent('Статус не передан');
    expect(statusSelect).not.toHaveTextContent('Завершена');
  });
});
