import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useLocation } from 'react-router-dom';
import { renderWithProviders } from '@/test/renderWithProviders';
import HeaderNew, { isThemeMenuInteraction } from '../HeaderNew';
import auth from '../../../stores/auth';

/**
 * HDR-FX-1 (header audit P2-7): the suite previously covered only the
 * theme-menu portal contract (3 tests). It now also pins: the banner
 * landmark (P2-1), the theme + profile menu keyboard/focus contracts
 * (P1-2/P1-3), the unread-badge live region (P2-2) and the registrar CTA
 * surface behavior (P2-4).
 */

const authState = {
  token: 'header-test-token',
  profile: {
    id: 1,
    username: 'admin',
    full_name: 'Admin User',
    role: 'Admin',
  } as Record<string, unknown>,
};

// Controllable unread count for the notification bell (P2-2 live region).
const unreadState = vi.hoisted(() => ({ count: 0 }));

vi.mock('../../../stores/auth.ts', () => ({
  default: {
    getState: () => authState,
    subscribe: (callback: (state: typeof authState) => void) => {
      callback(authState);
      return () => {};
    },
    clearToken: vi.fn(),
  },
  setProfile: vi.fn(),
}));

vi.mock('../../../contexts/NotificationCenterContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../contexts/NotificationCenterContext')>();
  return {
    ...actual,
    useNotificationCenter: () => ({
      inboxOpen: false,
      setInboxOpen: vi.fn(),
      getUnreadCount: () => unreadState.count,
    }),
  };
});

vi.mock('../../../components/pwa/CompactConnectionStatus', () => ({
  default: () => <div data-testid="connection-status" />,
}));

vi.mock('../../../components/search/GlobalSearchBar', () => ({
  default: () => <div data-testid="global-search" />,
}));

vi.mock('../../../components/chat/ChatButton', () => ({
  default: () => <div data-testid="chat-button" />,
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    info: vi.fn(),
    warn: vi.fn(),
    log: vi.fn(),
    debug: vi.fn(),
  },
}));

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-probe">{location.pathname}</div>;
}

function renderHeader(options: { role?: string; path?: string } = {}) {
  authState.profile = {
    id: 1,
    username: 'qa',
    full_name: 'QA User',
    role: options.role ?? 'Admin',
  };
  return renderWithProviders(
    <>
      <HeaderNew />
      <LocationProbe />
    </>,
    { routerProps: { initialEntries: [options.path ?? '/admin'] } },
  );
}

describe('HeaderNew theme menu', () => {
  beforeEach(() => {
    localStorage.clear();
    unreadState.count = 0;
    document.documentElement.removeAttribute('data-color-scheme');
    document.documentElement.setAttribute('data-theme', 'light');
    document.body.className = 'light-theme';
  });

  it('applies a selected theme from the portal menu', async () => {
    renderHeader();

    fireEvent.click(screen.getByRole('button', { name: 'Выбрать тему' }));
    // HDR-FX-1 (P1-3): scheme items are menuitemradio now, not bare buttons.
    fireEvent.click(await screen.findByRole('menuitemradio', { name: 'Темная' }));

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
      expect(document.body.classList.contains('dark-theme')).toBe(true);
      expect(screen.queryByRole('menuitemradio', { name: 'Темная' })).not.toBeInTheDocument();
    });
    // Codex round 4 (P2): selection unmounts the focused item - the trigger
    // must regain focus instead of dropping it to <body>.
    expect(screen.getByRole('button', { name: 'Выбрать тему' })).toHaveFocus();
  });

  it('treats clicks from a text node inside the portal menu as internal', () => {
    const triggerWrapper = document.createElement('div');
    const menuContainer = document.createElement('div');
    menuContainer.dataset.themeMenu = 'true';

    const label = document.createElement('span');
    const textNode = document.createTextNode('Темная');
    label.appendChild(textNode);
    menuContainer.appendChild(label);

    const event = {
      target: textNode,
      composedPath: () => [textNode, label, menuContainer, document.body, document],
    };

    expect(isThemeMenuInteraction(event, triggerWrapper)).toBe(true);
  });

  it('treats clicks outside both trigger and portal menu as external', () => {
    const triggerWrapper = document.createElement('div');
    const outside = document.createElement('button');

    const event = {
      target: outside,
      composedPath: () => [outside, document.body, document],
    };

    expect(isThemeMenuInteraction(event, triggerWrapper)).toBe(false);
  });
});

describe('HeaderNew chrome (HDR-FX-1)', () => {
  beforeEach(() => {
    localStorage.clear();
    unreadState.count = 0;
    document.documentElement.removeAttribute('data-color-scheme');
    document.documentElement.setAttribute('data-theme', 'light');
    document.body.className = 'light-theme';
  });

  it('renders the header as a banner landmark (P2-1)', () => {
    renderHeader();
    const banner = screen.getByRole('banner');
    expect(banner.tagName).toBe('HEADER');
  });

  it('theme menu: ArrowDown opens, items are menuitemradio with aria-checked, Escape closes and restores focus (P1-3)', async () => {
    renderHeader({ role: 'Admin', path: '/admin' });
    const trigger = screen.getByRole('button', { name: 'Выбрать тему' });

    // ArrowDown opens the menu from the trigger.
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const menu = screen.getByRole('menu', { name: 'Выбрать тему' });
    expect(menu).toBeInTheDocument();

    // The checked scheme (light, per beforeEach) is focused and aria-checked.
    const checked = screen.getByRole('menuitemradio', { name: 'Светлая' });
    expect(checked).toHaveAttribute('aria-checked', 'true');
    await waitFor(() => expect(checked).toHaveFocus());

    // Escape from inside the menu closes it and refocuses the trigger.
    fireEvent.keyDown(checked, { key: 'Escape' });
    expect(screen.queryByRole('menu', { name: 'Выбрать тему' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('theme menu: ArrowDown/ArrowUp cycle the scheme items with wrap-around (P1-3)', async () => {
    renderHeader({ role: 'Admin', path: '/admin' });
    const trigger = screen.getByRole('button', { name: 'Выбрать тему' });
    fireEvent.click(trigger);

    const names = ['Светлая', 'Темная', 'Авто'];
    const items = names.map((n) => screen.getByRole('menuitemradio', { name: n }));
    await waitFor(() => expect(items[0]).toHaveFocus());

    fireEvent.keyDown(items[0], { key: 'ArrowDown' });
    expect(items[1]).toHaveFocus();

    // Wrap-around from the first item backwards lands on the last.
    fireEvent.keyDown(items[1], { key: 'ArrowUp' });
    expect(items[0]).toHaveFocus();
    fireEvent.keyDown(items[0], { key: 'ArrowUp' });
    expect(items[items.length - 1]).toHaveFocus();
  });

  it('profile menu: opens with focus on the first item, arrows navigate, Escape closes and restores focus (P1-2)', async () => {
    renderHeader({ role: 'Admin', path: '/admin' });
    const trigger = screen.getByRole('button', { name: 'Профиль пользователя' });

    fireEvent.click(trigger);
    const firstItem = await screen.findByRole('menuitem', { name: 'Профиль' });
    await waitFor(() => expect(firstItem).toHaveFocus());

    fireEvent.keyDown(firstItem, { key: 'ArrowDown' });
    const logoutItem = screen.getByRole('menuitem', { name: 'Выйти' });
    expect(logoutItem).toHaveFocus();

    fireEvent.keyDown(logoutItem, { key: 'Escape' });
    expect(screen.queryByRole('menu', { name: 'Меню профиля' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('profile menu: logout clears the auth token (P1-2 surface)', () => {
    renderHeader({ role: 'Admin', path: '/admin' });
    fireEvent.click(screen.getByRole('button', { name: 'Профиль пользователя' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Выйти' }));
    expect(vi.mocked(auth.clearToken)).toHaveBeenCalled();
    expect(screen.queryByRole('menu', { name: 'Меню профиля' })).not.toBeInTheDocument();
  });

  it('unread badge announces the real count through a polite live region (P2-2)', () => {
    unreadState.count = 3;
    renderHeader({ role: 'Admin', path: '/admin' });
    expect(screen.getByRole('status')).toHaveTextContent('Непрочитанных: 3');

    // The visual badge is decorative for assistive tech and caps at 99+.
    unreadState.count = 150;
    renderHeader({ role: 'Admin', path: '/admin' });
    const status = screen.getAllByRole('status').find((el) => el.textContent === 'Непрочитанных: 150');
    expect(status).toBeDefined();
    expect(screen.getByText('99+')).toHaveAttribute('aria-hidden', 'true');
  });

  it('unread badge renders nothing when the count is zero, but the live region stays mounted (P2-2, Codex round 3)', () => {
    unreadState.count = 0;
    renderHeader({ role: 'Admin', path: '/admin' });
    // The badge is gone...
    expect(screen.queryByText('99+')).not.toBeInTheDocument();
    // ...while the live region remains mounted and reports the zero count,
    // so 1 -> 0 transitions are announced (region insertion would not be).
    expect(screen.getByRole('status')).toHaveTextContent('Непрочитанных: 0');
  });

  it('registrar CTA renders on every registrar surface and dispatches the wizard event in place (P2-4)', () => {
    const seen: string[] = [];
    const listener = (event: Event) => seen.push(event.type);
    window.addEventListener('openAppointmentWizard', listener);

    try {
      for (const path of ['/registrar', '/registrar/welcome', '/registrar/queue']) {
        const { unmount } = renderHeader({ role: 'Registrar', path });
        expect(screen.getByTitle('Новая запись')).toBeInTheDocument();
        expect(screen.getByTestId('location-probe')).toHaveTextContent(path);
        fireEvent.click(screen.getByTitle('Новая запись'));
        expect(seen).toContain('openAppointmentWizard');
        // P2-4: no navigation — the current view is preserved.
        expect(screen.getByTestId('location-probe')).toHaveTextContent(path);
        unmount();
      }
    } finally {
      window.removeEventListener('openAppointmentWizard', listener);
    }
  });

  it('registrar CTA is hidden off-surface and for non-registrar roles (P2-4)', () => {
    const { unmount } = renderHeader({ role: 'Registrar', path: '/clinical/profile' });
    expect(screen.queryByTitle('Новая запись')).not.toBeInTheDocument();
    unmount();

    renderHeader({ role: 'Admin', path: '/registrar' });
    expect(screen.queryByTitle('Новая запись')).not.toBeInTheDocument();
  });
});
