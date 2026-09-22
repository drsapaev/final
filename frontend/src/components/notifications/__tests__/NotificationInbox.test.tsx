import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import NotificationInbox from '../NotificationInbox';
import { LabDirtyGuardProvider, useLabDirtyGuard } from '../../laboratory/LabDirtyGuardContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

// PR 3351 (review round 3, P1): центр уведомлений переведён на единый
// guarded navigator — тесты гоняют переходы через реальный роутер
// (LocationProbe), а не через шпион window.history.pushState, которого
// MemoryRouter не использует.

const {
  store,
  getNotificationsByRole,
  markAsRead,
  markAsSeen,
  archiveNotification,
  markAllAsRead,
} = vi.hoisted(() => {
  const store = { notifications: [] as Array<ReturnType<typeof createNotification>> };
  return {
    store,
    getNotificationsByRole: vi.fn(() => store.notifications),
    markAsRead: vi.fn(async () => {}),
    markAsSeen: vi.fn(async () => {}),
    archiveNotification: vi.fn(async () => {}),
    markAllAsRead: vi.fn(async () => {}),
  };
});

vi.mock('../../../contexts/NotificationCenterContext', () => ({
  useNotificationCenter: () => ({
    getNotificationsByRole,
    markAsRead,
    markAsSeen,
    archiveNotification,
    markAllAsRead,
  }),
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

function createNotification(overrides = {}) {
  return {
    id: 'notification-1',
    title: 'Тестовое уведомление',
    message: 'Тестовое сообщение',
    type: 'system_alert',
    eventType: 'system_alert',
    createdAt: '2026-04-17T08:00:00Z',
    sequenceId: 1,
    isRead: false,
    isSeen: false,
    isArchived: false,
    ...overrides,
  };
}

/** Постоянный индикатор текущего пути: guarded navigate виден через роутер. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

/** Держит ссылку на регистрацию dirty-источника (паттерн LabDirtyGuardContext.test). */
function DirtySourceBridge({
  registration,
}: {
  registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
}) {
  const guard = useLabDirtyGuard();
  // Рендер-присваивание: тест читает registration.current после render().
  registration.current = (source) => (
    guard.registerDirtySource({ ...source, discard: () => { source.discard?.(); } })
  );
  return null;
}

type RenderOptions = {
  userRole?: string;
  initialEntries?: string[];
  registration?: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] };
};

function renderInbox({
  userRole = 'admin',
  initialEntries = ['/'],
  registration,
}: RenderOptions = {}) {
  const inbox = (
    <NotificationInbox userRole={userRole} onClose={() => {}} />
  );
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <LabDirtyGuardProvider>
          {registration ? (
            <DirtySourceBridge registration={registration} />
          ) : null}
          <LocationProbe />
          <Routes>
            <Route path="/lab" element={<div>lab page</div>} />
            <Route path="/messages" element={<div>messages page</div>} />
            <Route path="/admin/all-free-requests" element={<div>all free page</div>} />
            <Route path="/custom-target" element={<div>custom page</div>} />
            <Route path="/queue" element={<div>queue page</div>} />
            <Route path="/registrar/patients" element={<div>registrar patients</div>} />
            <Route path="/registrar" element={<div>registrar page</div>} />
            <Route path="/admin" element={<div>admin page</div>} />
            <Route path="/patient" element={<div>patient page</div>} />
            <Route path="*" element={<div>fallback</div>} />
          </Routes>
          {inbox}
        </LabDirtyGuardProvider>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe('NotificationInbox routing', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    store.notifications = [];
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it.each([
    { role: 'admin', type: 'all_free_requested', expectedTarget: '/admin/all-free-requests' },
    {
      role: 'admin',
      type: 'message_received',
      payloadSnapshot: { metadata: { conversation_id: 'conv-42' } },
      expectedTarget: '/messages?conversation=conv-42',
    },
    { role: 'doctor', type: 'lab_critical_result', expectedTarget: '/lab/results?critical=1' },
    { role: 'registrar', type: 'patient_registered', expectedTarget: '/registrar/patients' },
    { role: 'doctor', type: 'queue_position', expectedTarget: '/queue' },
    { role: 'admin', type: 'security_alert', expectedTarget: '/admin' },
    { role: 'admin', type: 'payment_notification', deepLink: '/patient', expectedTarget: '/patient' },
    { role: 'admin', type: 'system_alert', expectedTarget: '/admin' },
    { role: 'registrar', type: 'system_alert', expectedTarget: '/registrar' },
  ])(
    'navigates $type to $expectedTarget via the guarded navigator',
    async ({ role, type, expectedTarget, payloadSnapshot, deepLink }) => {
      store.notifications = [
        createNotification({
          id: `notification-${type}`,
          type,
          eventType: type,
          payloadSnapshot,
          deepLink,
        }),
      ];

      renderInbox({ userRole: role });
      fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));

      await waitFor(() => {
        expect(screen.getByTestId('location')).toHaveTextContent(expectedTarget);
      });

      expect(markAsSeen).toHaveBeenCalledTimes(1);
      expect(markAsRead).toHaveBeenCalledTimes(1);
    },
  );

  it('uses explicit deep link over type-based routing', async () => {
    store.notifications = [
      createNotification({
        id: 'notification-explicit-deep-link',
        type: 'all_free_requested',
        eventType: 'all_free_requested',
        deepLink: '/custom-target',
      }),
    ];

    renderInbox();
    fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/custom-target');
    });
  });

  it('does not navigate when notification type is unknown and no deep link exists', async () => {
    store.notifications = [
      createNotification({
        id: 'notification-unknown-type',
        type: 'unknown_runtime_event',
        eventType: 'unknown_runtime_event',
        deepLink: '',
      }),
    ];

    renderInbox({ initialEntries: ['/start-page'] });
    fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));

    await waitFor(() => {
      expect(markAsSeen).toHaveBeenCalledTimes(1);
      expect(markAsRead).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByTestId('location')).toHaveTextContent('/start-page');
  });

  it('does not push a duplicate entry when the target equals the current URL', async () => {
    store.notifications = [
      createNotification({
        id: 'notification-same-url',
        type: 'message_received',
        eventType: 'message_received',
        payloadSnapshot: { metadata: { conversation_id: 'conv-42' } },
      }),
    ];

    renderInbox({ initialEntries: ['/messages?conversation=conv-42'] });
    fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));

    await waitFor(() => {
      expect(markAsSeen).toHaveBeenCalledTimes(1);
    });
    // Тот же URL: короткое замыкание без перехода и без новой записи истории.
    expect(screen.getByTestId('location')).toHaveTextContent('/messages?conversation=conv-42');
  });

  // PR 3351 (review round 3, P1): центр уведомлений больше не обходит
  // route-level leave guard прямым pushState — клик по уведомлению при
  // dirty-черновике лаборатории открывает guard-диалог, а не молча
  // размонтирует LabPanel.
  it('keeps a dirty lab draft behind the guard dialog instead of silently leaving /lab', async () => {
    let reportDirty = true;
    const registration: { current?: ReturnType<typeof useLabDirtyGuard>['registerDirtySource'] } = {};
    store.notifications = [
      createNotification({
        id: 'notification-guarded',
        type: 'message_received',
        eventType: 'message_received',
        payloadSnapshot: { metadata: { conversation_id: 'conv-42' } },
      }),
    ];

    renderInbox({
      initialEntries: ['/lab'],
      registration,
    });
    await act(async () => {
      registration.current?.({
        id: 'report',
        isDirty: () => reportDirty,
        save: vi.fn().mockResolvedValue(undefined),
        discard: () => { reportDirty = false; },
      });
    });

    fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));

    // Guard-диалог открыт (кнопка «Выйти без сохранения» уникальна для него;
    // сам inbox-дропдаун тоже role=dialog, но без этих кнопок), переход НЕ
    // выполнен.
    const discardButton = await screen.findByRole('button', { name: 'Выйти без сохранения' });
    expect(discardButton).toBeVisible();
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    // Отмена: пользователь остаётся на /lab.
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Выйти без сохранения' })).not.toBeInTheDocument();
    });
    expect(screen.getByTestId('location')).toHaveTextContent('/lab');

    // Подтверждённый уход (discard) выполняет переход по цели уведомления.
    fireEvent.click(screen.getByLabelText(/Открыть уведомление:/i));
    await screen.findByRole('button', { name: 'Выйти без сохранения' });
    fireEvent.click(screen.getByRole('button', { name: 'Выйти без сохранения' }));
    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/messages?conversation=conv-42');
    });
    expect(screen.queryByRole('button', { name: 'Выйти без сохранения' })).not.toBeInTheDocument();
  });
});
