import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FinanceModal from '../FinanceModal.jsx';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';

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
    render(
      <MacOSThemeProvider>
        <ThemeProvider>
          <FinanceModal
            isOpen
            onClose={vi.fn()}
            onSave={vi.fn()}
            loading={false}
            patients={[]}
            doctors={[]}
          />
        </ThemeProvider>
      </MacOSThemeProvider>
    );

    const amountInput = screen.getByPlaceholderText('100000');

    expect(amountInput).toHaveAttribute('min', '1');
    expect(amountInput).toHaveAttribute('step', '1');
    expect(amountInput).toHaveAttribute('inputmode', 'numeric');
    expect(screen.getByText('Введите сумму целым числом в UZS. Например: 12500.')).toBeInTheDocument();
  });
});
