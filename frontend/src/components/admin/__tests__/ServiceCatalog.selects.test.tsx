import '@testing-library/jest-dom';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import ServiceCatalog from '../ServiceCatalog';
import { api } from '@/api/client';

// RQ-06.b — SYNTHETIC/DEV-DEMO fixtures only: service/category/doctor values are
// synthetic domain identifiers ("Синтетический …"), no PHI/PII values anywhere.
const syntheticCategories = [
  { id: 3, name_ru: 'Синтетическая категория', specialty: 'cardiology' }
];

const syntheticDoctors = [
  { id: 7, specialty: 'cardiology', user: { id: 70, full_name: 'Синтетический врач' } }
];

vi.mock('../../../api/client', () => {
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url === '/services') {
        return Promise.resolve({ data: [] });
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

const openAddServiceForm = async (user: ReturnType<typeof userEvent.setup>) => {
  render(
    <ThemeProvider>
      <ServiceCatalog />
    </ThemeProvider>
  );

  await waitFor(() => {
    expect(api.get).toHaveBeenCalledTimes(5);
  });

  // The header and the empty state both render an add button — click the first one.
  const addButtons = screen.getAllByRole('button', { name: 'Добавить услугу' });
  await user.click(addButtons[0]);

  await waitFor(() => {
    expect(screen.getByText('Добавление услуги')).toBeInTheDocument();
  });
};

const fillName = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  const label = screen.getByText('Название услуги *');
  const fieldContainer = label.closest('div');
  expect(fieldContainer).not.toBeNull();
  const nameInput = within(fieldContainer as HTMLElement).getByRole('textbox');
  await user.type(nameInput, name);
};

const selectByFormLabel = async (
  user: ReturnType<typeof userEvent.setup>,
  labelText: string,
  triggerName: RegExp | string | null,
  optionName: RegExp | string
) => {
  // The same text may also appear as a table column header — select only the
  // form label by its canonical class (admin2 ServiceForm labels).
  const label = screen
    .getAllByText(labelText)
    .find((el) => el.className.includes('admin-label-14-500-primary-mb-8'));
  expect(label).toBeDefined();
  const fieldContainer = (label as HTMLElement).closest('div');
  expect(fieldContainer).not.toBeNull();
  // triggerName=null reuses the only trigger in the field container. This is
  // needed after a numeric-value selection: the canonical Select cannot match
  // its string value against numeric option values (pre-existing display
  // quirk, registered separately), so the trigger keeps its placeholder name.
  const trigger = triggerName
    ? within(fieldContainer as HTMLElement).getByRole('button', { name: triggerName })
    : within(fieldContainer as HTMLElement).getByRole('button');
  await user.click(trigger);

  await waitFor(() => {
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });

  await user.click(screen.getByRole('option', { name: optionName }));
};

const selectCurrency = async (
  user: ReturnType<typeof userEvent.setup>,
  optionName: RegExp | string
) => {
  // Currency has no label of its own — scope by the price field container,
  // which holds the price input and the currency Select in one row.
  const label = screen
    .getAllByText('Цена')
    .find((el) => el.className.includes('admin-label-14-500-primary-mb-8'));
  expect(label).toBeDefined();
  const fieldContainer = (label as HTMLElement).closest('div');
  expect(fieldContainer).not.toBeNull();
  const trigger = within(fieldContainer as HTMLElement).getByRole('button', { name: 'UZS' });
  await user.click(trigger);

  await waitFor(() => {
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });

  await user.click(screen.getByRole('option', { name: optionName }));
};

describe('ServiceCatalog form selects deliver real values (RQ-06.b)', () => {
  it('delivers the selected category_id into the save payload (not [object Object])', async () => {
    const user = userEvent.setup();
    await openAddServiceForm(user);
    await fillName(user, 'Синтетическая услуга');

    await selectByFormLabel(user, 'Категория *', /Выберите категорию/, /Синтетическая категория/);

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({ category_id: 3 })
      );
    });

    const payload = (api.post as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(payload.category_id).not.toBeNaN();
    expect(String(payload.category_id)).not.toContain('object Object');
  });

  it('delivers the selected doctor_id into the save payload (not [object Object])', async () => {
    const user = userEvent.setup();
    await openAddServiceForm(user);
    await fillName(user, 'Синтетическая услуга');

    await selectByFormLabel(user, 'Врач (опционально)', /Все врачи/, /Синтетический врач/);

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({ doctor_id: 7 })
      );
    });

    const payload = (api.post as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(payload.doctor_id).not.toBeNaN();
    expect(String(payload.doctor_id)).not.toContain('object Object');
  });

  it('delivers the selected currency into the save payload (not [object Object])', async () => {
    const user = userEvent.setup();
    await openAddServiceForm(user);
    await fillName(user, 'Синтетическая услуга');

    await selectCurrency(user, 'USD');

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({ currency: 'USD' })
      );
    });

    const payload = (api.post as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(String(payload.currency)).not.toContain('object Object');
  });

  it('keeps explicit emptiness when the empty option is chosen again', async () => {
    const user = userEvent.setup();
    await openAddServiceForm(user);
    await fillName(user, 'Синтетическая услуга');

    await selectByFormLabel(user, 'Категория *', /Выберите категорию/, /Синтетическая категория/);
    // Return the select to its explicit empty option.
    await selectByFormLabel(user, 'Категория *', null, /Выберите категорию/);

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({ category_id: null })
      );
    });

    const payload = (api.post as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(payload.category_id).not.toBeNaN();
  });
});
