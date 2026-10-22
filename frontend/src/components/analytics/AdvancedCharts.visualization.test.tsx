import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { getAdvancedChartsData } from '../../pages/AnalyticsPage';

const chartMock = vi.hoisted(() => ({ configs: [] as unknown[] }));

vi.mock('chart.js/auto', () => ({
  default: class MockChart {
    constructor(_context: unknown, config: unknown) {
      chartMock.configs.push(config);
    }

    destroy() {}
  },
}));

import AdvancedCharts from './AdvancedCharts';

const visualization = {
  charts: {
    kpi: {
      visits: {
        type: 'line',
        data: { labels: ['2026-10-01'], datasets: [{ label: 'Visits', data: [3] }] },
        options: { plugins: { title: { text: 'Visits by day' } } },
      },
    },
    doctors: {
      performance: {
        type: 'bar',
        data: { labels: ['Doctor A'], datasets: [{ label: 'Visits', data: [2] }] },
        options: { plugins: { title: { text: 'Doctor performance' } } },
      },
    },
    patients: {
      age_groups: {
        type: 'doughnut',
        data: { labels: ['Adult'], datasets: [{ label: 'Patients', data: [1] }] },
        options: { plugins: { title: { text: 'Patient age groups' } } },
      },
    },
    revenue: {
      monthly: {
        type: 'line',
        data: { labels: ['2026-10'], datasets: [{ label: 'Revenue', data: [100] }] },
        options: { plugins: { title: { text: 'Revenue by month' } } },
      },
    },
  },
  summary: { total_charts: 4, chart_types: ['line', 'bar', 'doughnut'] },
};

const comprehensiveResponse = {
  period: { start_date: '2026-10-01', end_date: '2026-10-31', department: 'all' },
  data: {},
  visualization,
  generated_at: '2026-10-22T00:00:00Z',
};

describe('AdvancedCharts comprehensive visualization response', () => {
  beforeEach(() => {
    chartMock.configs.length = 0;
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as CanvasRenderingContext2D);
  });

  afterEach(() => vi.restoreAllMocks());

  it('renders Chart.js configs grouped by backend category', () => {
    render(<ThemeProvider><AdvancedCharts data={getAdvancedChartsData(comprehensiveResponse)} /></ThemeProvider>);

    expect(screen.getByRole('heading', { name: 'Visits by day' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Doctor performance' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Patient age groups' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Revenue by month' })).toBeInTheDocument();
    expect(chartMock.configs).toHaveLength(4);
    expect(chartMock.configs).toEqual(expect.arrayContaining([
      expect.objectContaining({ type: 'line' }),
      expect.objectContaining({ type: 'bar' }),
      expect.objectContaining({ type: 'doughnut' }),
    ]));
  });

  it('filters the grouped chart list when a category tab is selected', () => {
    render(<ThemeProvider><AdvancedCharts data={getAdvancedChartsData(comprehensiveResponse)} /></ThemeProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'KPI' }));

    expect(screen.getByRole('heading', { name: 'Visits by day' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Doctor performance' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Patient age groups' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Revenue by month' })).not.toBeInTheDocument();
  });
});
