import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { api } from '@/api/client';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';
import AdminDashboard from '../AdminDashboard';

vi.mock('@/api/client', () => ({
  api: { get: vi.fn() },
}));

const mockedGet = vi.mocked(api.get);

beforeEach(async () => {
  await i18n.changeLanguage('ru');
  mockedGet.mockReset();
  mockedGet.mockImplementation(async (url: string) => {
    if (url === '/admin/stats') {
      return { data: { appointmentsToday: 6, visitsToday: 2, totalPatients: 10 } } as never;
    }
    if (url.startsWith('/admin/morning-assignment/queue-summary?')) {
      return { data: { success: true, queues_count: 1, total_entries: 5 } } as never;
    }
    return { data: {} } as never;
  });
});

it('loads admin stats once and reuses them in the queue summary', async () => {
  render(
    <MemoryRouter initialEntries={['/admin']}>
      <ThemeProvider>
        <AdminDashboard />
      </ThemeProvider>
    </MemoryRouter>,
  );

  await waitFor(() => {
    const queueCard = screen.getByRole('group', { name: 'Сводка очереди' });
    expect(within(queueCard).getByText('5')).toBeInTheDocument();
    expect(within(queueCard).getByText('2')).toBeInTheDocument();
    expect(within(queueCard).getByText('4')).toBeInTheDocument();
    expect(mockedGet.mock.calls.filter(([url]) => url === '/admin/stats')).toHaveLength(1);
  });
});
