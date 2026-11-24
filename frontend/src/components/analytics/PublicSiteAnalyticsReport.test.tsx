import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PublicSiteAnalyticsReportData } from '../../api/adminPublicSiteAnalytics';
import PublicSiteAnalyticsReport from './PublicSiteAnalyticsReport';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../api/client', () => ({ api: { get } }));
vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ language: 'en-US', t: (key: string) => key }),
}));

const report = {
  enabled: true,
  days: [
    {
      clinic_day: '2026-11-23',
      site_views: 1234,
      phone_clicks: 12,
      booking_form_opens: 4,
      booking_requests_submitted: 1,
    },
    {
      clinic_day: '2026-11-22',
      site_views: 0,
      phone_clicks: 0,
      booking_form_opens: 0,
      booking_requests_submitted: 0,
    },
  ],
} satisfies PublicSiteAnalyticsReportData;

describe('PublicSiteAnalyticsReport', () => {
  beforeEach(() => {
    get.mockReset();
    get.mockResolvedValue({ data: report });
  });

  afterEach(cleanup);

  it('stays collapsed and requests data only after opening the native disclosure', async () => {
    render(<PublicSiteAnalyticsReport />);

    const summary = screen.getByText('publicSiteAnalytics.title');
    expect(summary.tagName).toBe('SUMMARY');
    expect(summary.closest('details')).not.toHaveAttribute('open');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();

    fireEvent.click(summary);

    expect(await screen.findByRole('table', { name: 'publicSiteAnalytics.title' })).toBeVisible();
    expect(get).toHaveBeenCalledExactlyOnceWith('/admin/public-site/analytics', {
      signal: expect.any(AbortSignal),
    });
  });

  it('renders daily totals in a semantic table inside a keyboard-focusable region', async () => {
    render(<PublicSiteAnalyticsReport />);
    fireEvent.click(screen.getByText('publicSiteAnalytics.title'));

    const region = await screen.findByRole('region', { name: 'publicSiteAnalytics.title' });
    expect(region).toHaveAttribute('tabindex', '0');
    region.focus();
    expect(region).toHaveFocus();

    const table = within(region).getByRole('table');
    expect(within(table).getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
      'publicSiteAnalytics.day',
      'publicSiteAnalytics.siteViews',
      'publicSiteAnalytics.phoneClicks',
      'publicSiteAnalytics.bookingFormOpens',
      'publicSiteAnalytics.bookingRequestsSubmitted',
    ]);
    expect(within(table).getByRole('rowheader', { name: 'Nov 23, 2026' })).toHaveAttribute('scope', 'row');
    expect(within(table).getByText('Nov 23, 2026')).toHaveAttribute('datetime', '2026-11-23');

    const [, latestDay, previousDay] = within(table).getAllByRole('row');
    expect(within(latestDay).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['1,234', '12', '4', '1']);
    expect(within(previousDay).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['0', '0', '0', '0']);
  });

  it('shows collection is paused while keeping historical totals available', async () => {
    get.mockResolvedValueOnce({ data: { ...report, enabled: false } });
    render(<PublicSiteAnalyticsReport />);
    fireEvent.click(screen.getByText('publicSiteAnalytics.title'));

    expect(await screen.findByRole('table')).toBeVisible();
    expect(screen.getByRole('status')).toHaveTextContent('publicSiteAnalytics.paused');
    expect(screen.getByRole('cell', { name: '1,234' })).toBeVisible();
  });

  it('allows a failed load to be retried and a successful report to be refreshed', async () => {
    get.mockRejectedValueOnce(new Error('Offline'));
    render(<PublicSiteAnalyticsReport />);
    fireEvent.click(screen.getByText('publicSiteAnalytics.title'));

    expect(await screen.findByRole('alert')).toHaveTextContent('publicSiteAnalytics.loadError');
    fireEvent.click(screen.getByRole('button', { name: 'publicSiteAnalytics.retry' }));
    expect(await screen.findByRole('table')).toBeVisible();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'publicSiteAnalytics.refresh' }));
    expect(await screen.findByRole('table')).toBeVisible();
    expect(get).toHaveBeenCalledTimes(3);
  });

  it('aborts an outstanding request when closed and fetches again when reopened', async () => {
    get.mockImplementationOnce(() => new Promise(() => {}));
    render(<PublicSiteAnalyticsReport />);
    const summary = screen.getByText('publicSiteAnalytics.title');
    fireEvent.click(summary);

    expect(await screen.findByRole('status')).toHaveTextContent('publicSiteAnalytics.loading');
    expect(screen.getByRole('button', { name: 'publicSiteAnalytics.refresh' })).toHaveAttribute('aria-disabled', 'true');
    const { signal } = get.mock.calls[0][1];
    fireEvent.click(summary);
    await waitFor(() => expect(signal.aborted).toBe(true));

    fireEvent.click(summary);
    expect(await screen.findByRole('table')).toBeVisible();
    expect(get).toHaveBeenCalledTimes(2);
  });
});
