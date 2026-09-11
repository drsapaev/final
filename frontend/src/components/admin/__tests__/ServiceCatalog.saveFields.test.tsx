import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import ServiceCatalog from '../ServiceCatalog';
import { api } from '@/api/client';

// RQ-06.a — SYNTHETIC/DEV-DEMO fixtures only: service/category/doctor values are
// synthetic domain identifiers ("Синтетический …"), no PHI/PII values anywhere.
const syntheticService = {
  id: 5,
  name: 'Синтетическая консультация',
  code: 'K01',
  service_code: 'K01',
  category_id: 3,
  price: 50000,
  currency: 'UZS',
  duration_minutes: 45,
  doctor_id: 7,
  active: true,
  department_key: 'cardiology',
  queue_tag: ''
};

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
        return Promise.resolve({ data: [syntheticService] });
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
    put: vi.fn(() => Promise.resolve({ data: { ...syntheticService } })),
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
};

const fillName = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  const label = screen.getByText('Название услуги *');
  const fieldContainer = label.closest('div');
  expect(fieldContainer).not.toBeNull();
  const nameInput = within(fieldContainer as HTMLElement).getByRole('textbox');
  await user.type(nameInput, name);
};

const fillNumberField = (labelText: string, value: string) => {
  // The same text may also appear as a table column header — select only the
  // form label by its canonical class (admin2 ServiceForm labels).
  const label = screen
    .getAllByText(labelText)
    .find((el) => el.className.includes('admin-label-14-500-primary-mb-8'));
  expect(label).toBeDefined();
  const fieldContainer = (label as HTMLElement).closest('div');
  expect(fieldContainer).not.toBeNull();
  const numberInput = within(fieldContainer as HTMLElement).getByRole('spinbutton');
  // Number inputs normalize intermediate values (parseInt(x) || 30), so char-by-char
  // typing races the controlled re-render. One change event with the full value
  // exercises the same onChange contract (parseFloat/parseInt(e.target.value)).
  fireEvent.change(numberInput, { target: { value } });
};

describe('ServiceCatalog save payload fields (RQ-06.a)', () => {
  it('preserves price/category/doctor/duration of an edited service in the update payload', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    await user.click(screen.getByRole('button', { name: 'Edit service Синтетическая консультация' }));
    await waitFor(() => {
      expect(screen.getByText('Редактирование услуги')).toBeInTheDocument();
    });

    // A deliberate user change (price) so the changes preview has a diff to confirm.
    fillNumberField('Цена', '65000');

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    // Edit mode shows the changes preview before saving. The confirm button's
    // accessible name comes from its aria-label («Подтвердить N изменений услуги»).
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Подтвердить \d+ изменений/ })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /Подтвердить \d+ изменений/ }));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        '/services/5',
        expect.objectContaining({
          price: 65000,
          category_id: 3,
          doctor_id: 7,
          duration_minutes: 45
        })
      );
    });
  });

  it('saves the typed price and duration of a new service instead of parsing the code field', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    const addButtons = screen.getAllByRole('button', { name: 'Добавить услугу' });
    await user.click(addButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Добавление услуги')).toBeInTheDocument();
    });

    await fillName(user, 'Синтетическая услуга');
    fillNumberField('Цена', '50000');
    fillNumberField('Длительность (мин)', '45');

    // New services save directly without the preview step.
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({
          price: 50000,
          duration_minutes: 45,
          category_id: null,
          doctor_id: null
        })
      );
    });
  });

  it('keeps explicit nulls for untouched numeric fields of a new service', async () => {
    const user = userEvent.setup();
    await renderCatalog();

    const addButtons = screen.getAllByRole('button', { name: 'Добавить услугу' });
    await user.click(addButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Добавление услуги')).toBeInTheDocument();
    });

    await fillName(user, 'Синтетическая услуга без цены');

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/services',
        expect.objectContaining({
          price: null,
          category_id: null,
          doctor_id: null,
          duration_minutes: 30
        })
      );
    });

    const payload = (api.post as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(payload.price).not.toBeNaN();
  });
});
