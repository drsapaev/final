import React from 'react';
import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import GlobalSearchBar from '../GlobalSearchBar';
import { canUseGlobalSearch } from '../globalSearchAccess';
import { api } from '../../../api/client';

/**
 * NURSE-V2 N2-2 (review P2 round 3 — PR 3333 + codex round): the global
 * search bar self-gates on the frontend mirror of the backend
 * GLOBAL_SEARCH_ROLES allowlist. Before the gate, the bar rendered
 * unconditionally inside HeaderNew — on the nurse home (/clinical/profile,
 * the N2-2 login landing) every typed query fired GET /global-search, hit
 * the backend role gate (Nurse is not in the allowlist) and the 403 was
 * swallowed into an empty "nothing found" list: a clinical control that is
 * guaranteed dead on that surface.
 *
 * The grant computation mirrors require_roles EXACTLY (codex finding):
 * is_superuser bypasses, otherwise the SINGLE primary role is compared
 * case-insensitively — profile.roles / role_name are never consulted,
 * because the backend never consults them either. The backend boundary
 * stays the source of truth for PHI; this gate only stops shipping the
 * dead control.
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
  // Every spelling the backend tuple carries must pass, case-insensitively
  // (the backend lowercases both sides before comparing).
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
    expect(canUseGlobalSearch({ role: null })).toBe(false);
  });

  it('mirrors the require_roles superuser bypass (codex: under-inclusive)', () => {
    // A superuser is admitted by the backend regardless of the stored
    // role — the gate must not hide a working control from them.
    expect(canUseGlobalSearch({ role: 'Patient', is_superuser: true })).toBe(true);
    expect(canUseGlobalSearch({ role: 'Nurse', is_superuser: true })).toBe(true);
    expect(canUseGlobalSearch({ role: 'Admin', is_superuser: false })).toBe(true);
    expect(canUseGlobalSearch({ role: 'nurse', is_superuser: false })).toBe(false);
  });

  it('consults ONLY the single primary role — never roles/role_name (codex: over-inclusive)', () => {
    // require_roles reads current_user.role alone; GET /auth/me exposes
    // exactly role + is_superuser. A roles array must not resurrect the
    // bar for a primary role the backend would 403.
    expect(canUseGlobalSearch({ role: 'Nurse', roles: ['Registrar'] })).toBe(false);
    expect(canUseGlobalSearch({ role: 'nurse', roles: ['nurse', 'doctor'] })).toBe(false);
    expect(canUseGlobalSearch({ role_name: 'Registrar' })).toBe(false);
    expect(canUseGlobalSearch({ role: 'Registrar', role_name: 'nurse' })).toBe(true);
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

  it('renders nothing when only a roles array claims a granted role (codex pin)', () => {
    // {role:'Nurse', roles:['Registrar']} — the backend checks the single
    // role column and would answer 403; the bar must not ship here.
    renderSearchBar({ id: 9, username: 'multi', role: 'nurse', roles: ['nurse', 'registrar'] });
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(apiGet).not.toHaveBeenCalled();
  });

  it('renders for a superuser regardless of the stored role (codex pin)', () => {
    renderSearchBar({ id: 11, username: 'root', role: 'Patient', is_superuser: true });
    expect(screen.getByRole('combobox')).toBeTruthy();
  });
});
