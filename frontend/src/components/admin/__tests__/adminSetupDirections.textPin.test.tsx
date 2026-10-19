import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  AdminQueueDirectionDto,
  AdminQueueDirectionsResponseDto,
} from '@/types/api';

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

const direction: AdminQueueDirectionDto = {
  profile: {
    id: 4,
    key: 'lab-key',
    title: 'Laboratory',
    title_ru: 'Лаборатория',
    queue_tags: ['lab'],
    department_key: 'lab',
    is_active: true,
    show_on_qr_page: true,
    display_order: 1,
    icon: null,
    color: null,
  },
  resolved_mode: 'booking',
  configuration_state: 'ready',
  configuration_reasons: [],
  effective_availability: 'available',
  effective_availability_reasons: [],
  booking_targets: [
    {
      owner_type: 'doctor',
      owner_id: 7,
      queue_tag: 'lab',
      label: 'Dr. Smith',
      is_active: true,
      eligible_for_new_booking: true,
      existing_daily_queue_ids: [301],
    },
  ],
  current_day_queues: [
    {
      daily_queue_id: 301,
      queue_tag: 'lab',
      owner_type: 'doctor',
      owner_id: 7,
    },
  ],
  public_availability: true,
  permanent_address_exists: false,
  precreate_by_tag: [
    {
      queue_tag: 'lab',
      state: 'eligible',
      can_precreate: true,
      active_service_count: 1,
      owner_type: 'doctor',
      owner_id: 7,
      existing_daily_queue_ids: [],
      reason_codes: ['single_active_service_owner'],
    },
  ],
  allowed_next_actions: [
    {
      kind: 'provision_permanent_address',
      entity_type: 'queue_profile',
      entity_id: 4,
      entity_key: 'lab-key',
    },
  ],
};

const emptyUnattached = { queue_tags: [], services: [], resources: [] };

function response(
  selectedDirection: AdminQueueDirectionDto = direction,
  asOfDay = '2026-10-18',
): AdminQueueDirectionsResponseDto {
  return {
    as_of_day: asOfDay,
    directions: [selectedDirection],
    unattached: emptyUnattached,
  };
}

function entryMethods(supported = false) {
  return {
    direction_key: 'lab-key',
    entry_methods: [
      { method: 'session_qr', supported: true },
      { method: 'permanent_address', supported },
    ],
  };
}

function mockReadSide() {
  mockedGet.mockImplementation(async (url: string) => {
    if (url.startsWith('/queue/admin/directions')) return { data: response() };
    if (url.startsWith('/services?limit=1000')) return { data: [serviceRow] };
    if (url.startsWith('/queues/profiles?active_only=false')) {
      return { data: { profiles: [profileRow] } };
    }
    if (url.includes('/entry-methods')) return { data: entryMethods() };
    if (url.startsWith('/queue/admin/queue-resources')) return { data: [] };
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

describe('AdminSetupDirections — backend facts and lazy details', () => {
  it('renders server-owned direction facts before making any per-profile QR request', async () => {
    renderScreen();

    const card = await screen.findByTestId('setup-checklist-row-lab');
    expect(within(card).getByTestId('setup-direction-targets')).toHaveTextContent('Dr. Smith');
    expect(within(card).getByTestId('setup-direction-queues')).toHaveTextContent('Очередь №301');
    expect(within(card).getByTestId('setup-row-public-availability')).toHaveTextContent('Доступно для записи');
    expect(screen.getByTestId('setup-day-context')).toHaveTextContent('2026-10-18');
    expect(mockedGet).toHaveBeenCalledWith('/queue/admin/directions');
    expect(mockedGet.mock.calls.some(([url]) => String(url).includes('/entry-methods'))).toBe(false);
    expect(mockedGet.mock.calls.some(([url]) => String(url).startsWith('/services'))).toBe(false);

    await userEvent.setup().click(screen.getByTestId('setup-qr-expand-lab'));
    await waitFor(() => {
      expect(mockedGet.mock.calls.some(([url]) => String(url).includes('/entry-methods'))).toBe(true);
    });
    expect(await screen.findByTestId('setup-qr-block-lab')).toBeVisible();
    expect(screen.getByTestId('setup-checklist-row-lab')).toBeVisible();
  });

  it('shows overview, conflict, and resource ownership from the DTO without inferring a doctor', async () => {
    const overview: AdminQueueDirectionDto = {
      ...direction,
      profile: { ...direction.profile, is_active: false, show_on_qr_page: true },
      resolved_mode: 'overview',
      configuration_state: 'conflict',
      effective_availability: 'unavailable',
      public_availability: false,
      booking_targets: [
        {
          owner_type: 'resource',
          owner_id: 7,
          queue_tag: 'lab',
          label: 'Lab room',
          is_active: true,
          eligible_for_new_booking: false,
          existing_daily_queue_ids: [],
        },
      ],
      allowed_next_actions: [
        {
          kind: 'review_configuration',
          entity_type: 'department',
          entity_id: 9,
          entity_key: 'lab',
        },
      ],
    };
    mockedGet.mockImplementation(async (url: string) =>
      url.startsWith('/queue/admin/directions') ? { data: response(overview) } : { data: {} },
    );

    renderScreen();
    const card = await screen.findByTestId('setup-checklist-row-lab');
    expect(card).toHaveTextContent('Конфликт настроек');
    expect(card).toHaveTextContent('Внутренний обзор нескольких очередей');
    expect(within(card).getByTestId('setup-row-profile-active')).toHaveTextContent('В архиве');
    expect(within(card).getByTestId('setup-row-public-setting')).toHaveTextContent('Публикация настроена');
    expect(within(card).getByTestId('setup-row-public-availability')).toHaveTextContent('Сейчас недоступно');
    expect(within(card).getByTestId('setup-direction-targets')).toHaveTextContent('Ресурс');
    expect(within(card).getByTestId('setup-action-without-editor')).toBeVisible();
    expect(card).not.toHaveTextContent('Создать врача');
  });

  it('keeps direction facts visible and retries a failed QR read', async () => {
    let reads = 0;
    mockedGet.mockImplementation(async (url: string) => {
      if (url.startsWith('/queue/admin/directions')) return { data: response() };
      if (url.includes('/entry-methods')) {
        reads += 1;
        if (reads === 1) throw new Error('synthetic read failure');
        return { data: entryMethods() };
      }
      return { data: {} };
    });

    renderScreen();
    await screen.findByTestId('setup-checklist-row-lab');
    const user = userEvent.setup();
    await user.click(screen.getByTestId('setup-qr-expand-lab'));
    expect(await screen.findByTestId('setup-qr-read-retry-lab')).toBeVisible();
    expect(screen.getByTestId('setup-direction-queues')).toBeVisible();

    await user.click(screen.getByTestId('setup-qr-read-retry-lab'));
    expect(await screen.findByTestId('setup-qr-block-lab')).toBeVisible();
    expect(reads).toBe(2);
  });

  it('ignores an older day response after a newer selection has loaded', async () => {
    let resolveInitial!: (value: { data: AdminQueueDirectionsResponseDto }) => void;
    const initial = new Promise<{ data: AdminQueueDirectionsResponseDto }>((resolve) => {
      resolveInitial = resolve;
    });
    mockedGet.mockImplementation(async (url: string) => {
      if (url === '/queue/admin/directions') return initial;
      if (url === '/queue/admin/directions?day=2026-10-17') {
        return { data: response({ ...direction, profile: { ...direction.profile, title_ru: 'Новый день' } }, '2026-10-17') };
      }
      return { data: {} };
    });

    renderScreen();
    fireEvent.change(screen.getByTestId('setup-day-select'), { target: { value: '2026-10-17' } });
    expect(await screen.findByText('Новый день')).toBeVisible();
    expect(mockedGet).toHaveBeenCalledWith('/queue/admin/directions?day=2026-10-17');
    resolveInitial({ data: response({ ...direction, profile: { ...direction.profile, title_ru: 'Старый ответ' } }, '2026-10-18') });
    await waitFor(() => expect(screen.queryByText('Старый ответ')).toBeNull());
    expect(screen.getByTestId('setup-day-context')).toHaveTextContent('2026-10-17');
  });
});

describe('AdminSetupDirections — setup entry points', () => {
  it('starts the existing resource wizard path without requiring a tag', async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByTestId('setup-checklist-row-lab');

    await user.click(screen.getByTestId('setup-wizard-open'));
    const resourceAxis = screen.getByTestId('setup-wizard-axis-resource');
    expect(resourceAxis).not.toBeDisabled();
    await user.click(resourceAxis);
    expect(screen.getByTestId('setup-wizard-step-services')).toBeVisible();
  });

  it('loads resource editor inputs only when the resource view is opened', async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByTestId('setup-checklist-row-lab');
    expect(mockedGet.mock.calls.some(([url]) => String(url).startsWith('/services'))).toBe(false);

    await user.click(screen.getByTestId('setup-view-resources'));
    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith('/services?limit=1000'));
    expect(screen.getByTestId('setup-back-to-checklist')).toBeVisible();
  });
});
