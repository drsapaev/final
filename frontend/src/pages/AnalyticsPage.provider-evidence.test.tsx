import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { api } from '../api/client';
import { ThemeProvider } from '../contexts/ThemeContext';
import AnalyticsPage from './AnalyticsPage';

vi.mock('../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

describe('provider financial statistics', () => {
  it.each([
    { commission: null, successRate: null, showsMetrics: false },
    { commission: 0, successRate: 0, showsMetrics: true },
  ])('shows evidence with a commission of $commission', async ({ commission, successRate, showsMetrics }) => {
    vi.mocked(api.get).mockImplementation(async (url) => ({
      data: String(url).startsWith('/analytics/payment-providers?') ? {
        summary: { total_commission: commission, total_revenue: 60, total_transactions: 1 },
        providers: { synthetic: { name: 'Synthetic payment provider', total_amount: 60, success_rate: successRate } },
      } : {},
    }));

    render(<MemoryRouter><ThemeProvider><AnalyticsPage /></ThemeProvider></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'misc.an_tab_providers' }));

    expect(await screen.findByText('misc.an_prov_section_yield_title')).toBeVisible();
    expect(screen.getAllByText('Synthetic payment provider')).not.toHaveLength(0);
    if (showsMetrics) {
      expect(screen.getByText('misc.an_prov_metric_commission')).toBeVisible();
      expect(screen.getByText('0.0%')).toBeVisible();
    } else {
      expect(screen.queryByText('misc.an_prov_metric_commission')).not.toBeInTheDocument();
      expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
      expect(screen.getByText('misc.an_compare_empty')).toBeVisible();
    }
  });
});
