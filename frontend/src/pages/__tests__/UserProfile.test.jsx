import React, { StrictMode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../theme/macosTheme.jsx';

const { apiGet, apiPut, setAuthProfile, getAuthState } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  setAuthProfile: vi.fn(),
  getAuthState: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  api: {
    get: apiGet,
    put: apiPut,
  },
}));

vi.mock('../../stores/auth', () => ({
  getState: getAuthState,
  setProfile: setAuthProfile,
}));

vi.mock('../../components/settings/NotificationPreferences.jsx', () => ({
  default: () => <div>Notification Preferences Stub</div>,
}));

vi.mock('../../components/security/TwoFactorManager', () => ({
  default: () => <div>Two Factor Stub</div>,
}));

import UserProfile, { __resetSelfProfileCacheForTests } from '../UserProfile.jsx';

function renderUserProfile() {
  return render(
    <MacOSThemeProvider>
      <ThemeProvider>
        <UserProfile />
      </ThemeProvider>
    </MacOSThemeProvider>
  );
}

function renderUserProfileInStrictMode() {
  return render(
    <StrictMode>
      <MacOSThemeProvider>
        <ThemeProvider>
          <UserProfile />
        </ThemeProvider>
      </MacOSThemeProvider>
    </StrictMode>
  );
}

describe('UserProfile page', () => {
  const profileResponse = {
    id: 20,
    username: 'registrar',
    full_name: 'Registrar User',
    first_name: 'Registrar',
    last_name: 'User',
    middle_name: '',
    email: 'registrar@example.com',
    phone: '+998901112233',
    avatar_url: '',
    bio: 'Profile bio',
    website: 'https://example.test',
    language: 'ru',
    timezone: 'Asia/Tashkent',
    nationality: 'Uzbek',
    date_of_birth: '1990-01-01T00:00:00',
    gender: 'female',
    role: 'Receptionist',
    is_active: true,
    is_superuser: false,
    email_verified: true,
    phone_verified: false,
    created_at: '2026-01-01T10:00:00',
    updated_at: '2026-02-01T10:00:00',
    last_login: '2026-03-02T10:00:00',
    two_factor_enabled: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    __resetSelfProfileCacheForTests();
    getAuthState.mockReturnValue({ token: 'token', profile: profileResponse });
    apiGet.mockResolvedValue({ data: profileResponse });
    apiPut.mockResolvedValue({
      data: {
        ...profileResponse,
        full_name: 'Registrar Updated',
        phone: '+998909999999',
        bio: 'Updated bio',
      },
    });
  });

  it('loads and renders self profile form on info tab', async () => {
    renderUserProfile();

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith('/authentication/profile');
    });

    expect(await screen.findByDisplayValue('Registrar User')).toBeInTheDocument();
    expect(screen.getByDisplayValue('registrar@example.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('+998901112233')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /сохранить профиль/i })).toBeDisabled();
  });

  it('saves edited profile and syncs auth store', async () => {
    renderUserProfile();

    const fullNameInput = await screen.findByDisplayValue('Registrar User');
    const phoneInput = screen.getByDisplayValue('+998901112233');
    const bioInput = screen.getByDisplayValue('Profile bio');

    fireEvent.change(fullNameInput, { target: { value: 'Registrar Updated' } });
    fireEvent.change(phoneInput, { target: { value: '+998909999999' } });
    fireEvent.change(bioInput, { target: { value: 'Updated bio' } });
    fireEvent.click(screen.getByRole('button', { name: /сохранить профиль/i }));

    await waitFor(() => {
      expect(apiPut).toHaveBeenCalledWith(
        '/authentication/profile',
        expect.objectContaining({
          full_name: 'Registrar Updated',
          phone: '+998909999999',
          bio: 'Updated bio',
        })
      );
    });

    expect(setAuthProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: 'Registrar Updated',
        phone: '+998909999999',
      })
    );
    expect(await screen.findByText(/профиль успешно сохранен/i)).toBeInTheDocument();
  });

  it('reuses one in-flight self profile request across strict mode remounts', async () => {
    let resolveRequest;
    apiGet.mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve;
      })
    );

    renderUserProfileInStrictMode();

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledTimes(1);
    });

    resolveRequest({ data: profileResponse });

    expect(await screen.findByDisplayValue('Registrar User')).toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledTimes(1);
  });

  it('falls back to cached auth profile when self profile is rate limited', async () => {
    apiGet.mockRejectedValueOnce({
      response: {
        status: 429,
        data: { detail: 'Превышен лимит запросов: 100 за 3600 секунд' },
      },
    });

    renderUserProfile();

    expect(await screen.findByDisplayValue('Registrar User')).toBeInTheDocument();
    expect(await screen.findByText(/показаны кешированные данные профиля/i)).toBeInTheDocument();
  });
});
