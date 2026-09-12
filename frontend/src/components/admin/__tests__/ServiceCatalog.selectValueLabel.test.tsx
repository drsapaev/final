import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import ServiceCatalog from '../ServiceCatalog';
import { api } from '@/api/client';

// RQ-06.d — SYNTHETIC/DEV-DEMO fixtures only: category/doctor/service values are
// synthetic domain identifiers ("Синтетический …"), no PHI/PII values anywhere.
const syntheticCategories = [
  { id: 3, name_ru: 'Синтетическая категория', specialty: 'cardiology' }
];

const syntheticDoctors = [
  { id: 7, specialty: 'cardiology', user: { id: 70, full_name: 'Синтетический врач' } }
];

const syntheticServices = [
  {
    id: 1,
    name: 'Синтетическая услуга А',
    category_id: 3,
    doctor_id: 7,
    department_key: 'cardio_dept',
    active: true
  }
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
        return Promise.resolve({ data: syntheticDoctors });
      }

      if (url === '/departments' || url === '/admin/departments') {
        return Promise.resolve({ data: { data: [] } });
      }

      if (url.startsWith('/queues/profiles')) {
        return Promise.resolve({ data: { profiles: [] } });
      }

      return Promise.resolve({ data: [] });
    }),
    post: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
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
};

const getFormSelectTrigger = (labelText: string) => {
  // The same text may also appear as a table column header — select only the
  // form label by its canonical class (admin2 ServiceForm labels).
  const label = screen
    .getAllByText(labelText)
    .find((el) => el.className.includes('admin-label-14-500-primary-mb-8'));
  expect(label).toBeDefined();
  const fieldContainer = (label as HTMLElement).closest('div');
  expect(fieldContainer).not.toBeNull();
  return within(fieldContainer as HTMLElement).getByRole('button');
};

describe('ServiceCatalog selects keep the chosen label visible (RQ-06.d)', () => {
  it('shows the chosen category label in the form trigger after selection (not the default placeholder)', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    const addButtons = screen.getAllByRole('button', { name: 'Добавить услугу' });
    await user.click(addButtons[0]);
    await waitFor(() => {
      expect(screen.getByText('Добавление услуги')).toBeInTheDocument();
    });

    const trigger = getFormSelectTrigger('Категория *');
    expect(trigger).toHaveAccessibleName(/Выберите категорию/);

    await user.click(trigger);
    await waitFor(() => {
      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('option', { name: /Синтетическая категория/ }));

    // RQ-06.d: the trigger must keep showing the chosen label. With numeric
    // option values the strict === lookup misses the string form state and the
    // trigger falls back to the default placeholder.
    const triggerAfter = getFormSelectTrigger('Категория *');
    expect(triggerAfter).toHaveAccessibleName(/Синтетическая категория/);
    expect(triggerAfter).not.toHaveAccessibleName('Select…');
  });

  it('shows the chosen doctor label in the form trigger after selection (not the default placeholder)', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    const addButtons = screen.getAllByRole('button', { name: 'Добавить услугу' });
    await user.click(addButtons[0]);
    await waitFor(() => {
      expect(screen.getByText('Добавление услуги')).toBeInTheDocument();
    });

    const trigger = getFormSelectTrigger('Врач (опционально)');
    expect(trigger).toHaveAccessibleName(/Все врачи/);

    await user.click(trigger);
    await waitFor(() => {
      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('option', { name: /Синтетический врач/ }));

    const triggerAfter = getFormSelectTrigger('Врач (опционально)');
    expect(triggerAfter).toHaveAccessibleName(/Синтетический врач/);
    expect(triggerAfter).not.toHaveAccessibleName('Select…');
  });

  it('shows the chosen category label in the list filter trigger after selection (not the default placeholder)', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    const filterTrigger = screen.getByRole('button', { name: 'Все категории' });
    await user.click(filterTrigger);
    await waitFor(() => {
      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('option', { name: /Синтетическая категория/ }));

    expect(screen.getByText('Синтетическая услуга А')).toBeInTheDocument();
    expect(screen.queryByText('Синтетическая услуга Б')).not.toBeInTheDocument();

    // RQ-06.d: the filter trigger keeps the chosen category name instead of
    // falling back to the default placeholder after the selection.
    expect(filterTrigger).toHaveAccessibleName(/Синтетическая категория/);
    expect(filterTrigger).not.toHaveAccessibleName('Select…');
  });

  it('keeps the chosen labels visible when editing an existing service (edit-load pin)', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    await user.click(screen.getByRole('button', { name: 'Edit service Синтетическая услуга А' }));
    await waitFor(() => {
      expect(screen.getByText('Редактирование услуги')).toBeInTheDocument();
    });

    // Form state init must stay aligned with the string option contract:
    // the edit form reopens with the previously selected category/doctor
    // labels visible, not the placeholder fallback.
    expect(getFormSelectTrigger('Категория *')).toHaveAccessibleName(/Синтетическая категория/);
    expect(getFormSelectTrigger('Врач (опционально)')).toHaveAccessibleName(/Синтетический врач/);
  });
});
