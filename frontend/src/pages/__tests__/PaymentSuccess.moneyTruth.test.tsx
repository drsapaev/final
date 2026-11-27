/**
 * PATSUCC-FE-001 + PATSUCC-FE-003 (owner registry #4063; review-group
 * audit comment 6739106445) — money truth and template honesty on the
 * payment confirmation surface.
 *
 * - PATSUCC-FE-001: the page's `formatAmount` divides UZS/KZT amounts
 *   by 100 against a major-unit API (`Payment.amount` is Numeric(12,2),
 *   the provider tiyin conversion happens only at the provider protocol
 *   boundary, the invoice chain stores the amount as given) — the
 *   initiating widget (`PaymentWidget.formatAmount`) formats the SAME
 *   amount with Intl.NumberFormat and NO division. A 150 000 UZS
 *   payment shows as «150 000 UZS» at initiation and «1 500» on the
 *   post-payment receipt — a 100× understatement fed into the on-screen
 *   amount, the txt receipt, the share text and the print receipt.
 * - PATSUCC-FE-003: the print-receipt HTML is a backtick template
 *   string whose `{t('misc.ps_…')}` occurrences are plain text, never
 *   invoked — the printed receipt shows literal `{t(…)}` placeholders
 *   as its headings.
 *
 * Contract after the repair:
 * - the rendered amount equals the Intl.NumberFormat rendering the
 *   initiating widget produces for the same value (no /100);
 * - the composed print HTML contains no literal `{t(` substring and
 *   renders the same translation keys the page uses.
 *
 * Red-first: on the pre-fix source the Intl amount never appears (the
 * /100 value does) and the print HTML carries `{t(` literals — both
 * RED on main.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MouseEventHandler, PropsWithChildren } from 'react';
import { MemoryRouter } from 'react-router-dom';

const { printCapture } = vi.hoisted(() => ({ printCapture: { html: '' } }));

vi.mock('../../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../../utils/printWindow', () => ({
  openPrintableWindow: vi.fn(({ html }: { html: string }) => { printCapture.html = html; }),
}));
vi.mock('../../services/notify', () => ({ notify: { success: vi.fn(), error: vi.fn() } }));
vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string, options?: Record<string, unknown>) => key }),
}));
vi.mock('../../components/ui/macos', () => ({
  Alert: ({ children }: PropsWithChildren) => <div>{children}</div>,
  Badge: ({ children }: PropsWithChildren) => <span>{children}</span>,
  Button: ({ children, onClick, ...props }: PropsWithChildren<Record<string, unknown>>) => (
    <button type="button" onClick={onClick as MouseEventHandler<HTMLButtonElement>} {...props}>
      {children}
    </button>
  ),
  Card: ({ children }: PropsWithChildren) => <section>{children}</section>,
  CardContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
}));

import { api } from '../../api/client';
import PaymentSuccess from '../PaymentSuccess';

const PAID_UZS = { id: 123, amount: 150000, currency: 'UZS', status: 'paid', provider: 'click', description: '', created_at: '2026-11-20T10:00:00Z' };

beforeEach(() => {
  vi.clearAllMocks();
  printCapture.html = '';
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url === '/payments/123') return Promise.resolve({ data: PAID_UZS });
    if (url === '/payments/123/receipt') return Promise.resolve({ data: { receipt_url: 'https://cdn.example/receipt.pdf' } });
    return Promise.resolve({ data: {} });
  });
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/payment/success?payment_id=123']}>
      <PaymentSuccess />
    </MemoryRouter>,
  );
}

// Intl formats currency groups with NBSP — match the rendering shape,
// not a fragile exact string.
const MAJOR_UZS = /150[\s\u00A0]+000[\s\u00A0]+UZS/;
const UNDERSTATED = /1[\s\u00A0]+500/;

describe('PATSUCC-FE-001/003 — the payment surface tells the money truth', () => {
  it('a 150 000 UZS payment renders the widget-consistent major-unit amount (no /100)', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByText(MAJOR_UZS).length).toBeGreaterThan(0));
    // The understated /100 value (1 500) never appears.
    expect(screen.queryByText(UNDERSTATED)).toBeNull();
  });

  it('the print receipt has no literal {t( placeholders and renders the localized headings', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByText(MAJOR_UZS).length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole('button', { name: /Печать/ }));

    await waitFor(() => expect(printCapture.html).not.toBe(''));
    expect(printCapture.html).not.toContain('{t(');
    expect(printCapture.html).toContain('misc.ps_kvitantsiya_ob_oplate');
    expect(printCapture.html).toContain('misc.ps_platezh');
    expect(printCapture.html).toContain('misc.ps_status');
    // The receipt body carries the widget-consistent amount too.
    expect(MAJOR_UZS.test(printCapture.html)).toBe(true);
  });
});
