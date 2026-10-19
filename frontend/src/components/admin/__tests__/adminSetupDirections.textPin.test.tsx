import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
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
  setSessionInvalidationListener: vi.fn(),
}));

vi.mock('../QueueProfilesManager', () => ({ default: () => null }));
vi.mock('../ServiceCatalog', () => ({ default: () => null }));

import { api } from '../../../api/client';
import AdminSetupDirections from '../AdminSetupDirections';
import AdminServices from '../AdminServices';
import {
  buildSetupReturnLocation as buildServicesReturnLocation,
  parseSetupReturnContext as parseServicesReturnContext,
} from '../AdminServices';
import UserManagementPage, {
  buildSetupReturnLocation as buildUsersReturnLocation,
  parseSetupReturnContext as parseUsersReturnContext,
} from '../UserManagement';

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

const LocationProbe = () => {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <output data-testid="route-location">{location.pathname}{location.search}</output>
      <button type="button" onClick={() => navigate(-1)}>Back</button>
      <button type="button" onClick={() => navigate(1)}>Forward</button>
    </div>
  );
};

const renderScreen = (initialEntries = ['/admin/setup-directions']) =>
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <LocationProbe />
        <AdminSetupDirections />
      </MemoryRouter>
    </ThemeProvider>,
  );

const renderServices = (initialEntries: string[]) =>
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <LocationProbe />
        <AdminServices />
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
  it('offers fixed editor links when no directions are configured', async () => {
    mockedGet.mockImplementation(async (url: string) =>
      url.startsWith('/queue/admin/directions')
        ? { data: { as_of_day: '2026-10-18', directions: [], unattached: emptyUnattached } }
        : { data: {} },
    );

    renderScreen();

    const links = within(await screen.findByTestId('setup-empty-editors')).getAllByRole('link');
    const urls = links.map((link) => new URL(link.getAttribute('href') || '', 'http://localhost'));
    expect(urls.map(({ pathname }) => pathname)).toEqual([
      '/admin/services',
      '/admin/services',
      '/admin/users',
    ]);
    expect(urls[0].searchParams.get('servicesTab')).toBe('catalog');
    expect(urls[1].searchParams.get('servicesTab')).toBe('queue-profiles');
    for (const url of urls) {
      expect(url.searchParams.get('setupReturn')).toBe('queue-directions-v1');
      expect(url.searchParams.get('setupSection')).toBe('checklist');
      expect(url.searchParams.has('setupEntityKind')).toBe(false);
    }
  });

  it('restores a valid deep link and selected profile after mounting', async () => {
    renderScreen(['/admin/setup-directions?section=checklist&day=2026-10-17&profile=lab-key']);

    const card = await screen.findByTestId('setup-checklist-row-lab');
    expect(card).toHaveAttribute('data-selected', 'true');
    expect(screen.getByTestId('setup-day-select')).toHaveValue('2026-10-17');
    expect(mockedGet).toHaveBeenCalledWith('/queue/admin/directions?day=2026-10-17');
    const routeUrl = new URL(screen.getByTestId('route-location').textContent || '', 'http://localhost');
    expect(routeUrl.pathname).toBe('/admin/setup-directions');
    expect(routeUrl.searchParams.get('section')).toBe('checklist');
    expect(routeUrl.searchParams.get('day')).toBe('2026-10-17');
    expect(routeUrl.searchParams.get('profile')).toBe('lab-key');
  });

  it('stores the selected direction in the URL', async () => {
    const user = userEvent.setup();
    renderScreen(['/admin/setup-directions?section=checklist&day=2026-10-17']);

    const card = await screen.findByTestId('setup-checklist-row-lab');
    expect(card).not.toHaveAttribute('data-selected', 'true');
    await user.click(screen.getByTestId('setup-select-profile-lab-key'));

    const routeUrl = new URL(screen.getByTestId('route-location').textContent || '', 'http://localhost');
    expect(routeUrl.pathname).toBe('/admin/setup-directions');
    expect(routeUrl.searchParams.get('section')).toBe('checklist');
    expect(routeUrl.searchParams.get('day')).toBe('2026-10-17');
    expect(routeUrl.searchParams.get('profile')).toBe('lab-key');
    expect(card).toHaveAttribute('data-selected', 'true');
  });

  it('restores the resource section from a direct URL after mounting', async () => {
    renderScreen(['/admin/setup-directions?section=resources&day=2026-10-17&profile=lab-key']);

    expect(await screen.findByTestId('setup-back-to-checklist')).toBeVisible();
    expect(screen.getByTestId('route-location')).toHaveTextContent(
      '/admin/setup-directions?section=resources&day=2026-10-17&profile=lab-key',
    );
    expect(mockedGet).toHaveBeenCalledWith('/services?limit=1000');
  });

  it('normalizes invalid page context and never selects the first profile as a fallback', async () => {
    renderScreen(['/admin/setup-directions?section=not-a-section&day=2026-02-30&profile=missing']);

    const card = await screen.findByTestId('setup-checklist-row-lab');
    await waitFor(() => {
      expect(screen.getByTestId('route-location')).toHaveTextContent(
        '/admin/setup-directions?section=checklist',
      );
    });
    expect(card).not.toHaveAttribute('data-selected', 'true');
    expect(screen.queryByTestId('setup-wizard-open')).toBeNull();
    expect(screen.queryByTestId('setup-wizard')).toBeNull();
  });

  it('removes a setup-page day with ISO year zero', async () => {
    renderScreen(['/admin/setup-directions?section=checklist&day=0000-01-01']);

    await screen.findByTestId('setup-checklist-row-lab');
    await waitFor(() => {
      const routeUrl = new URL(screen.getByTestId('route-location').textContent || '', 'http://localhost');
      expect(routeUrl.searchParams.has('day')).toBe(false);
    });
  });

  it('rejects duplicated setup state parameters before reading a day or selecting a profile', async () => {
    renderScreen([
      '/admin/setup-directions?section=resources&section=checklist&day=2026-10-17&day=2026-10-18&profile=lab-key&profile=other',
    ]);

    const card = await screen.findByTestId('setup-checklist-row-lab');
    await waitFor(() => {
      const routeUrl = new URL(screen.getByTestId('route-location').textContent || '', 'http://localhost');
      expect(routeUrl.searchParams.getAll('section')).toEqual(['checklist']);
      expect(routeUrl.searchParams.has('day')).toBe(false);
      expect(routeUrl.searchParams.has('profile')).toBe(false);
    });
    expect(card).not.toHaveAttribute('data-selected', 'true');
    expect(mockedGet).toHaveBeenCalledWith('/queue/admin/directions');
  });

  it('keeps section, day, and profile in browser history across editor navigation context changes', async () => {
    const user = userEvent.setup();
    renderScreen(['/admin/setup-directions?section=checklist&profile=lab-key']);
    await screen.findByTestId('setup-checklist-row-lab');

    fireEvent.change(screen.getByTestId('setup-day-select'), { target: { value: '2026-10-17' } });
    await waitFor(() => expect(screen.getByTestId('route-location')).toHaveTextContent('day=2026-10-17'));
    await user.click(screen.getByTestId('setup-view-resources'));
    await waitFor(() => expect(screen.getByTestId('route-location')).toHaveTextContent('section=resources'));
    expect(screen.getByTestId('route-location')).toHaveTextContent('profile=lab-key');
    expect(screen.getByTestId('route-location')).toHaveTextContent('day=2026-10-17');

    await user.click(screen.getByRole('button', { name: 'Back' }));
    await waitFor(() => expect(screen.getByTestId('route-location')).toHaveTextContent('section=checklist'));
    expect(screen.getByTestId('route-location')).toHaveTextContent('day=2026-10-17');
    await user.click(screen.getByRole('button', { name: 'Back' }));
    await waitFor(() => expect(screen.getByTestId('route-location')).not.toHaveTextContent('day='));
    await user.click(screen.getByRole('button', { name: 'Forward' }));
    await waitFor(() => expect(screen.getByTestId('route-location')).toHaveTextContent('day=2026-10-17'));
    await user.click(screen.getByRole('button', { name: 'Forward' }));
    await waitFor(() => expect(screen.getByTestId('route-location')).toHaveTextContent('section=resources'));
  });

  it('creates only fixed editor destinations and does not infer an ambiguous tag', async () => {
    const ownershipDirection: AdminQueueDirectionDto = {
      ...direction,
      allowed_next_actions: [{
        kind: 'configure_ownership',
        entity_type: 'queue_tag',
        entity_id: null,
        entity_key: null,
      }],
    };
    mockedGet.mockImplementation(async (url: string) =>
      url.startsWith('/queue/admin/directions') ? { data: response(ownershipDirection) } : { data: {} },
    );
    renderScreen(['/admin/setup-directions?section=checklist&day=2026-10-17&profile=lab-key']);

    const actionLinks = within(await screen.findByTestId('setup-action-editors')).getAllByRole('link');
    const catalogUrl = new URL(actionLinks[0].getAttribute('href') || '', 'http://localhost');
    const usersUrl = new URL(actionLinks[1].getAttribute('href') || '', 'http://localhost');
    expect(catalogUrl.pathname).toBe('/admin/services');
    expect(catalogUrl.searchParams.get('servicesTab')).toBe('catalog');
    expect(usersUrl.pathname).toBe('/admin/users');
    for (const url of [catalogUrl, usersUrl]) {
      expect(url.searchParams.get('setupReturn')).toBe('queue-directions-v1');
      expect(url.searchParams.get('setupSection')).toBe('checklist');
      expect(url.searchParams.get('setupProfile')).toBe('lab-key');
      expect(url.searchParams.get('setupDay')).toBe('2026-10-17');
      expect(url.searchParams.has('setupEntityKind')).toBe(false);
    }
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

describe('queue setup editor return context', () => {
  it('preserves shared return context while switching queue profiles to catalog and back', async () => {
    const user = userEvent.setup();
    renderServices([
      '/admin/services?servicesTab=queue-profiles&setupReturn=queue-directions-v1&setupSection=checklist&setupProfile=lab-key&setupDay=2026-10-17&setupEntityKind=queue_profile&setupEntityKey=lab-key',
    ]);

    expect(await screen.findByTestId('queue-setup-return-link')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Справочник услуг' }));

    const afterCatalog = new URL(screen.getByTestId('route-location').textContent || '', 'http://localhost');
    expect(afterCatalog.searchParams.get('servicesTab')).toBe('catalog');
    expect(afterCatalog.searchParams.get('setupReturn')).toBe('queue-directions-v1');
    expect(afterCatalog.searchParams.get('setupProfile')).toBe('lab-key');
    expect(afterCatalog.searchParams.get('setupSection')).toBe('checklist');
    expect(afterCatalog.searchParams.get('setupDay')).toBe('2026-10-17');
    expect(afterCatalog.searchParams.has('setupEntityKind')).toBe(false);
    expect(afterCatalog.searchParams.has('setupEntityKey')).toBe(false);
    expect(screen.getByTestId('queue-setup-return-link')).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Вкладки регистратуры' }));

    const afterQueueProfiles = new URL(screen.getByTestId('route-location').textContent || '', 'http://localhost');
    expect(afterQueueProfiles.searchParams.get('servicesTab')).toBe('queue-profiles');
    expect(afterQueueProfiles.searchParams.get('setupReturn')).toBe('queue-directions-v1');
    expect(afterQueueProfiles.searchParams.get('setupProfile')).toBe('lab-key');
    expect(afterQueueProfiles.searchParams.get('setupSection')).toBe('checklist');
    expect(afterQueueProfiles.searchParams.get('setupDay')).toBe('2026-10-17');
    expect(afterQueueProfiles.searchParams.has('setupEntityKind')).toBe(false);
    expect(afterQueueProfiles.searchParams.has('setupEntityKey')).toBe(false);
    expect(screen.getByTestId('queue-setup-return-link')).toBeVisible();
  });

  it('accepts typed service context and always builds a fixed setup return path', () => {
    const search = '?servicesTab=catalog&setupReturn=queue-directions-v1&setupSection=resources&setupProfile=lab-key&setupDay=2026-10-17&setupEntityKind=service&setupEntityId=11';
    const context = parseServicesReturnContext(search, 'service-catalog');

    expect(context).toMatchObject({
      destination: 'service-catalog',
      profileKey: 'lab-key',
      section: 'resources',
      day: '2026-10-17',
      entity: { kind: 'service', id: 11 },
    });
    expect(buildServicesReturnLocation(context!)).toEqual({
      pathname: '/admin/setup-directions',
      search: '?profile=lab-key&section=resources&day=2026-10-17',
    });
  });

  it('rejects malformed, duplicate, and non-decimal editor context', () => {
    expect(parseServicesReturnContext(
      '?setupReturn=queue-directions-v1&setupSection=checklist&setupEntityKind=service&setupEntityId=1e2',
      'service-catalog',
    )).toBeNull();
    expect(parseServicesReturnContext(
      '?setupReturn=queue-directions-v1&setupReturn=https%3A%2F%2Fevil.test&setupSection=checklist',
      'service-catalog',
    )).toBeNull();
    expect(parseUsersReturnContext(
      '?setupReturn=queue-directions-v1&setupSection=checklist&setupEntityKind=doctor&setupEntityId=1e2',
    )).toBeNull();
    expect(parseUsersReturnContext(
      '?setupReturn=queue-directions-v1&setupSection=checklist&setupDay=2026-02-30',
    )).toBeNull();
  });

  it('rejects year-zero setup dates in the services return-context parser', () => {
    const search = '?setupReturn=queue-directions-v1&setupSection=checklist&setupDay=0000-01-01';

    expect(parseServicesReturnContext(search, 'service-catalog')).toBeNull();
  });

  it('rejects year-zero setup dates in the users return-context parser', () => {
    const search = '?setupReturn=queue-directions-v1&setupSection=checklist&setupDay=0000-01-01';

    expect(parseUsersReturnContext(search)).toBeNull();
  });

  it('accepts supported editor return-context year boundaries', () => {
    for (const day of ['0001-01-01', '9999-12-31']) {
      const search = `?setupReturn=queue-directions-v1&setupSection=checklist&setupDay=${day}`;

      expect(parseServicesReturnContext(search, 'service-catalog')?.day).toBe(day);
      expect(parseUsersReturnContext(search)?.day).toBe(day);
    }
  });

  it('preserves typed queue-tag context for the existing user editor return link', () => {
    const context = parseUsersReturnContext(
      '?setupReturn=queue-directions-v1&setupSection=checklist&setupProfile=lab-key&setupDay=2026-10-17&setupEntityKind=queue_tag&setupEntityKey=lab',
    );
    expect(context).toMatchObject({
      destination: 'user-management',
      entity: { kind: 'queue_tag', key: 'lab' },
    });
    expect(buildUsersReturnLocation(context!)).toEqual({
      pathname: '/admin/setup-directions',
      search: '?profile=lab-key&section=checklist&day=2026-10-17',
    });
    expect(parseUsersReturnContext(
      '?setupReturn=queue-directions-v1&setupSection=checklist&setupEntityKind=queue_tag&setupEntityKey=lab&setupEntityKey=other',
    )).toBeNull();
  });

  it('renders a safe return link in the existing user editor', async () => {
    mockedGet.mockImplementation(async (url: string) => {
      if (url === '/users/users') {
        return { data: { users: [], total: 0, total_pages: 1 } };
      }
      if (url === '/roles/options') return { data: { options: [] } };
      return { data: {} };
    });
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={[
          '/admin/users?setupReturn=queue-directions-v1&setupSection=resources&setupProfile=lab-key&setupDay=2026-10-17&setupEntityKind=queue_tag&setupEntityKey=lab',
        ]}>
          <UserManagementPage />
        </MemoryRouter>
      </ThemeProvider>,
    );

    const returnLink = await screen.findByTestId('queue-setup-return-link');
    expect(returnLink).toHaveAttribute(
      'href',
      '/admin/setup-directions?profile=lab-key&section=resources&day=2026-10-17',
    );
    expect(mockedGet).toHaveBeenCalledWith('/users/users', expect.anything());
  });
});
