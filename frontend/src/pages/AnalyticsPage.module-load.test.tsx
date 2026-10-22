import { describe, expect, it } from 'vitest';

describe('AnalyticsPage module initialization', () => {
  it('loads the route module and its chart dependencies without throwing', async () => {
    const analyticsPage = await import('./AnalyticsPage');

    expect(analyticsPage.default).toEqual(expect.any(Function));
  });

  it('extracts grouped chart configs from the comprehensive endpoint response', async () => {
    const { getAdvancedChartsData } = await import('./AnalyticsPage');
    const chartConfig = {
      type: 'line',
      data: { labels: ['2026-10-01'], datasets: [{ label: 'Visits', data: [3] }] },
      options: { plugins: { title: { text: 'Visits' } } },
    };
    const response = {
      period: { start_date: '2026-10-01', end_date: '2026-10-31' },
      data: {},
      visualization: {
        charts: {
          kpi: { visits: chartConfig },
          doctors: {},
          patients: {},
          revenue: {},
        },
        summary: { total_charts: 1 },
      },
      generated_at: '2026-10-22T00:00:00Z',
    };

    expect(getAdvancedChartsData(response)).toEqual(response.visualization);
    expect(getAdvancedChartsData({ ...response, visualization: {} })).toBeNull();
  });
});
