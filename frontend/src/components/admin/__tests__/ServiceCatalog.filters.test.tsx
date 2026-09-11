import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import ServiceCatalog from '../ServiceCatalog';
import { api } from '@/api/client';

// RQ-06.c — SYNTHETIC/DEV-DEMO fixtures only: service/category/department values
// are synthetic domain identifiers ("Синтетический …"), no PHI/PII values anywhere.
const syntheticCategories = [
  { id: 3, name_ru: 'Синтетическая категория', specialty: 'cardiology' },
  { id: 4, name_ru: 'Синтетическая категория Б', specialty: 'dermatology' }
];

const syntheticServices = [
  {
    id: 1,
    name: 'Синтетическая услуга А',
    category_id: 3,
    department_key: 'cardio_dept',
    active: true
  },
  {
    id: 2,
    name: 'Синтетическая услуга Б',
    category_id: 4,
    department_key: 'derma_dept',
    active: true
  }
];

const syntheticDepartments = [
  { key: 'cardio_dept', name_ru: 'Синтетическое отделение А' },
  { key: 'derma_dept', name_ru: 'Синтетическое отделение Б' }
];

vi.mock('../../../api/client', () => {
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url === '/services') {
        return Promise.resolve({ data: syntheticServices });
      }

      if (url === '/services/categories') {
        return Promise.resolve({ data: syntheticCategories });
      }

      if (url === '/services/admin/doctors') {
        return Promise.resolve({ data: [] });
      }

      if (url === '/admin/departments') {
        return Promise.resolve({ data: { data: syntheticDepartments } });
      }

      if (url.startsWith('/queues/profiles')) {
        return Promise.resolve({ data: { profiles: [] } });
      }

      return Promise.resolve({ data: [] });
    }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  };

  return {
    default: apiMock,
    api: apiMock,
    apiClient: apiMock
  };
});

afterEach(() => {
  vi.clearAllMocks();
});

const renderCatalog = async () => {
  render(
    <ThemeProvider>
      <ServiceCatalog />
    </ThemeProvider>
  );

  await waitFor(() => {
    expect(api.get).toHaveBeenCalledTimes(5);
  });

  await new Promise((resolve) => setTimeout(resolve, 300));

  // Both synthetic services are listed while every filter is on "all".
  expect(screen.getByText('Синтетическая услуга А')).toBeInTheDocument();
  expect(screen.getByText('Синтетическая услуга Б')).toBeInTheDocument();
};

const pickFilterOption = async (
  user: ReturnType<typeof userEvent.setup>,
  triggerName: string | RegExp,
  optionName: string | RegExp
) => {
  await user.click(screen.getByRole('button', { name: triggerName }));

  await waitFor(() => {
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });

  await user.click(screen.getByRole('option', { name: optionName }));
};

describe('ServiceCatalog list filters deliver real values (RQ-06.c)', () => {
  it('specialty filter keeps only matching services (not [object Object] empty list)', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    await pickFilterOption(user, 'Все специальности', 'Кардиология');

    // Selected value must reach the filter state as a real specialty string,
    // so the cardiology service stays and the other one is filtered out.
    expect(screen.getByText('Синтетическая услуга А')).toBeInTheDocument();
    expect(screen.queryByText('Синтетическая услуга Б')).not.toBeInTheDocument();
  });

  it('category filter keeps only matching services (not [object Object] empty list)', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    await pickFilterOption(user, 'Все категории', 'Синтетическая категория');

    expect(screen.getByText('Синтетическая услуга А')).toBeInTheDocument();
    expect(screen.queryByText('Синтетическая услуга Б')).not.toBeInTheDocument();
  });

  it('department filter keeps only matching services (not [object Object] empty list)', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    await pickFilterOption(user, 'Все отделения', 'Синтетическое отделение А');

    expect(screen.getByText('Синтетическая услуга А')).toBeInTheDocument();
    expect(screen.queryByText('Синтетическая услуга Б')).not.toBeInTheDocument();
  });

  it('returns the full list when the specialty filter is reset to "all"', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    await pickFilterOption(user, 'Все специальности', 'Кардиология');
    expect(screen.queryByText('Синтетическая услуга Б')).not.toBeInTheDocument();

    await pickFilterOption(user, 'Кардиология', 'Все специальности');

    expect(screen.getByText('Синтетическая услуга А')).toBeInTheDocument();
    expect(screen.getByText('Синтетическая услуга Б')).toBeInTheDocument();
  });
});
