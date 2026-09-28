/**
 * RQ-17 — text pin «ноль технических ключей» (brief §5) + checklist render.
 *
 * Brief §5: «Ноль технических ключей как обязательное знание пользователя —
 * фиксируется тестом-пином на тексты форм пути». This suite pins, on the
 * rendered path forms:
 *  1. the S-14 wizard has NO free-text inputs at all — the executor axis,
 *     tag choice and every step is a select/button/link (tag values come
 *     from the API);
 *  2. the QueueResource create form's tag control is a select fed with
 *     existing tags (no manual queue_tag entry);
 *  3. the checklist renders per-tag rows with recomputed statuses.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

import { api } from '../../../api/client';
import AdminSetupDirections from '../AdminSetupDirections';

const mockedGet = vi.mocked(api.get);

const serviceRow = {
  id: 11,
  name: 'Лабораторный анализ',
  active: true,
  requires_doctor: false,
  queue_tag: 'lab',
  doctor_id: null,
};

const profileRow = {
  key: 'lab-key',
  title_ru: 'Лаборатория',
  is_active: true,
  show_on_qr_page: true,
  queue_tags: ['lab'],
};

function mockReadSide() {
  mockedGet.mockImplementation(async (url: string) => {
    // более специфичная ветка ДО общего префикса /services:
    // read-side активных Doctor-записей (brief §3(а), round-3 P1)
    if (url.startsWith('/services/admin/doctors')) {
      return { data: [{ id: 7, specialty: 'lab', cabinet: '101', active: true }] };
    }
    if (url.startsWith('/services')) {
      return { data: [serviceRow] };
    }
    if (url.startsWith('/queues/profiles')) {
      return { data: { profiles: [profileRow] } };
    }
    if (url.startsWith('/queue/admin/queue-resources')) {
      return { data: [] };
    }
    if (url.includes('/entry-methods')) {
      return {
        data: {
          direction_key: 'lab-key',
          entry_methods: [
            { method: 'session_qr', supported: true },
            { method: 'permanent_address', supported: false },
          ],
        },
      };
    }
    return { data: {} };
  });
}

const renderScreen = () =>
  render(
    <ThemeProvider>
      <MemoryRouter>
        <AdminSetupDirections />
      </MemoryRouter>
    </ThemeProvider>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  mockReadSide();
});

describe('AdminSetupDirections — checklist render (statuses recomputed from API)', () => {
  it('renders a per-tag row with axis and step statuses', async () => {
    renderScreen();

    const row = await waitFor(() =>
      expect(screen.getByTestId('setup-checklist-row-lab')).toBeVisible(),
    );
    expect(row).toBeDefined();
    // doctorless-нога инварианта видна для ресурсной оси? нет — оси ещё нет;
    // (а) не готово, (б) готово: 1 активная услуга, профиль владеет тегом.
    expect(screen.getByTestId('setup-row-services')).toHaveTextContent('1');
    expect(screen.getByTestId('setup-row-profile')).toBeVisible();
    // (д) честный статус из entry-methods: provision не сделан → «не готово»
    expect(screen.getByTestId('setup-row-permanent-address')).toBeVisible();
  });
});

describe('AdminSetupDirections — wizard «с пустой формы» (round-3 P1)', () => {
  it('resource axis can START without an existing tag (deferred tag choice)', async () => {
    const user = userEvent.setup();
    renderScreen();

    await waitFor(() =>
      expect(screen.getByTestId('setup-checklist-row-lab')).toBeVisible(),
    );

    await user.click(screen.getByTestId('setup-wizard-open'));
    // кнопка resource-оси НЕ заблокирована пустым выбором тега —
    // совершенно новое направление стартует с пустой формы
    const axisButton = screen.getByTestId('setup-wizard-axis-resource');
    expect(axisButton).not.toBeDisabled();
    await user.click(axisButton);
    expect(screen.getByTestId('setup-wizard-step-services')).toBeVisible();
  });
});

describe('AdminSetupDirections — «ноль технических ключей» (§5 text pin)', () => {
  it('wizard forms contain NO free-text inputs — everything is select/button/link', async () => {
    const user = userEvent.setup();
    renderScreen();

    await waitFor(() =>
      expect(screen.getByTestId('setup-checklist-row-lab')).toBeVisible(),
    );

    await user.click(screen.getByTestId('setup-wizard-open'));
    const wizard = screen.getByTestId('setup-wizard');
    expect(wizard.querySelectorAll('input')).toHaveLength(0);

    // шаг «услуги»: только ссылка/кнопки — никакой ручной ввод
    await user.click(screen.getByTestId('setup-wizard-axis-doctor'));
    expect(screen.getByTestId('setup-wizard-step-services').querySelectorAll('input')).toHaveLength(0);

    // шаг «отображение»: только ссылка/кнопки
    await user.click(screen.getByTestId('setup-wizard-services-next'));
    expect(screen.getByTestId('setup-wizard-step-display').querySelectorAll('input')).toHaveLength(0);

    // тег выбирается из существующих значений — контрол-селектор, не ввод
    await user.click(screen.getByTestId('setup-wizard-close'));
    await user.click(screen.getByTestId('setup-wizard-open'));
    expect(screen.getByTestId('setup-wizard-tag-select')).toBeVisible();
  });

  it('QueueResource create form: tag is a select of existing values, not a text input', async () => {
    const user = userEvent.setup();
    renderScreen();

    await waitFor(() =>
      expect(screen.getByTestId('setup-checklist-row-lab')).toBeVisible(),
    );

    await user.click(screen.getByTestId('setup-view-resources'));
    await user.click(screen.getByTestId('qr-resource-create-toggle'));

    const form = screen.getByTestId('qr-resource-create-form');
    // тег — выбор из существующих значений (§4(3))
    expect(screen.getByTestId('qr-resource-tag-select')).toBeVisible();
    // среди текстовых полей формы нет поля тега: единственные input —
    // code (авто-префикс из тега), имя и числовые/кабинет
    const inputs = Array.from(form.querySelectorAll('input'));
    const tagLike = inputs.filter((input) => {
      const label = input.closest('label')?.textContent || '';
      return /тег|queue_tag/i.test(label) || /queue_tag/i.test(input.name);
    });
    expect(tagLike).toHaveLength(0);
  });
});
