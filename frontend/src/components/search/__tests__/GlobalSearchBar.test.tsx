import React from 'react';
import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import GlobalSearchBar from '../GlobalSearchBar';
import { canUseGlobalSearch } from '../globalSearchAccess';
import { api } from '../../../api/client';

/**
 * NURSE-V2 N2-2 (review P2 round 3 — PR #3333): the global search bar
 * self-gates on the frontend mirror of the backend GLOBAL_SEARCH_ROLES
 * allowlist. Before the gate, the bar rendered unconditionally inside
 * HeaderNew — on the nurse home (/clinical/profile, the N2-2 login
 * landing) every typed query fired GET /global-search, hit the backend
 * role gate (Nurse is not in the allowlist) and the 403 was swallowed
 * into an empty "nothing found" list: a clinical control that is
 * guaranteed dead on that surface. The backend boundary stays the source
 * of truth for PHI; this gate only stops shipping the dead control.
 */

const authState = {
  token: 'gsb-test-token',
  profile: null as Record<string, unknown> | null,
};

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

vi.mock('../../../utils/logger', () => ({
  default: {
    info: vi.fn(),
    warn: vi.fn(),
    log: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
  },
}));

const apiGet = vi.spyOn(api, 'get').mockResolvedValue({
  data: { patients: [], visits: [], labResults: [] },
});

function renderSearchBar(profile: Record<string, unknown> | null) {
  authState.profile = profile;
  return renderWithProviders(<GlobalSearchBar />, {
    routerProps: { initialEntries: ['/clinical/profile'] },
  });
}

beforeEach(() => {
  apiGet.mockClear();
});

describe('canUseGlobalSearch (backend GLOBAL_SEARCH_ROLES mirror)', () => {
  // Every spelling the backend tuple carries must pass, case-insensitively.
  const backendAllowlist = [
    'Admin', 'Registrar', 'Doctor', 'Cashier', 'Lab', 'Laboratory',
    'cardio', 'cardiology', 'Cardiologist', 'derma', 'Dermatologist',
    'dentist', 'Dentist',
  ];
  it.each(backendAllowlist)('allows the backend spelling %s', (role) => {
    expect(canUseGlobalSearch({ role })).toBe(true);
    expect(canUseGlobalSearch({ role: role.toLowerCase() })).toBe(true);
  });

  it.each(['Nurse', 'nurse', 'Patient', 'patient', 'manager', ''])(
    'denies the non-search role %s',
    (role) => {
      expect(canUseGlobalSearch({ role })).toBe(false);
    },
  );

  it('denies a missing profile (fail closed) and empty payloads', () => {
    expect(canUseGlobalSearch(null)).toBe(false);
    expect(canUseGlobalSearch(undefined)).toBe(false);
    expect(canUseGlobalSearch({})).toBe(false);
    expect(canUseGlobalSearch({ role: null, role_name: undefined })).toBe(false);
  });

  it('honors a roles array: any granted role is enough', () => {
    expect(canUseGlobalSearch({ roles: ['nurse', 'doctor'] })).toBe(true);
    expect(canUseGlobalSearch({ roles: ['nurse'] })).toBe(false);
    expect(canUseGlobalSearch({ roles: [] })).toBe(false);
    expect(canUseGlobalSearch({ roles: ['nurse', 42, null] })).toBe(false);
  });

  it('falls back to role_name when role is absent', () => {
    expect(canUseGlobalSearch({ role_name: 'Registrar' })).toBe(true);
    expect(canUseGlobalSearch({ role_name: 'nurse' })).toBe(false);
  });
});

describe('GlobalSearchBar role gate (NURSE-V2 N2-2)', () => {
  it('renders nothing for a Nurse profile and never calls the API', () => {
    const { container } = renderSearchBar({
      id: 7,
      username: 'nurse_a',
      role: 'Nurse',
    });
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(container.textContent).toBe('');
    expect(apiGet).not.toHaveBeenCalled();
  });

  it('renders nothing without a profile (fail closed)', () => {
    renderSearchBar(null);
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(apiGet).not.toHaveBeenCalled();
  });

  it('renders the search combobox for a search-capable role (Doctor)', () => {
    renderSearchBar({ id: 3, username: 'doc_a', role: 'Doctor' });
    expect(screen.getByRole('combobox')).toBeTruthy();
  });

  it('renders for a mixed multi-role profile that includes a granted role', () => {
    renderSearchBar({ id: 9, username: 'multi', role: 'nurse', roles: ['nurse', 'registrar'] });
    expect(screen.getByRole('combobox')).toBeTruthy();
  });
});
