import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';
import HeaderNew, { isThemeMenuInteraction } from '../HeaderNew.jsx';

const authState = {
  token: 'header-test-token',
  profile: {
    id: 1,
    username: 'admin',
    full_name: 'Admin User',
    role: 'Admin',
  },
};

vi.mock('../../../stores/auth.js', () => ({
  default: {
    getState: () => authState,
    subscribe: (callback) => {
      callback(authState);
      return () => {};
    },
    clearToken: vi.fn(),
  },
  setProfile: vi.fn(),
}));

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

function renderHeader() {
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <MacOSThemeProvider>
        <ThemeProvider>
          <HeaderNew />
        </ThemeProvider>
      </MacOSThemeProvider>
    </MemoryRouter>
  );
}

describe('HeaderNew theme menu', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-color-scheme');
    document.documentElement.setAttribute('data-theme', 'light');
    document.body.className = 'light-theme';
  });

  it('applies a selected theme from the portal menu', async () => {
    renderHeader();

    fireEvent.click(screen.getByRole('button', { name: 'Выбрать тему' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Темная' }));

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
      expect(document.body.classList.contains('dark-theme')).toBe(true);
      expect(screen.queryByRole('button', { name: 'Темная' })).not.toBeInTheDocument();
    });
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
