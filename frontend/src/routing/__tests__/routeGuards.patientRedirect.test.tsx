/**
 * Phase 0 follow-up (Codex P1, rounds 2-3): where does a missing token land?
 * The redirect target follows the EXPIRED PRINCIPAL, not the route — the
 * patient panel route is shared with support staff, so route metadata cannot
 * identify whose session died. An expired PATIENT lands on /patient/login
 * (the phone/OTP entry point); expired staff and anonymous visitors keep
 * /login — including staff whose session dies ON the shared patient panel.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RouteAccessBoundary } from '../routeGuards';
import { clearToken, getExpiredPrincipalWasPatient, setToken } from '../../stores/auth';

vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'ru',
    setLanguage: vi.fn(),
    availableLanguages: [{ code: 'ru', name: 'Русский', flag: 'RU' }],
    t: (key: string) => key,
  }),
}));

type BoundaryRoute = NonNullable<Parameters<typeof RouteAccessBoundary>[0]['route']>;

// patient-home is intentionally SHARED: Patient + Admin/Registrar/Doctor.
const PATIENT_HOME_ROUTE: BoundaryRoute = {
  id: 'patient-home',
  group: 'clinical',
  auth: 'role-scoped',
  roles: ['Admin', 'Registrar', 'Doctor', 'Patient'],
  homeForRoles: ['patient'],
};

const REGISTRAR_HOME_ROUTE: BoundaryRoute = {
  id: 'registrar-home',
  group: 'clinical',
  auth: 'role-scoped',
  roles: ['Admin', 'Registrar', 'Receptionist'],
  homeForRoles: ['registrar', 'receptionist'],
};

function renderAt(path: string, route: BoundaryRoute): string[] {
  const seen: string[] = [];
  const LocationProbe = () => {
    const { pathname } = useLocation();
    if (seen[seen.length - 1] !== pathname) {
      seen.push(pathname);
    }
    return null;
  };
  render(
    <MemoryRouter initialEntries={[path]}>
      {/* Real app structure: the boundary renders under a matched route and
          UNMOUNTS once its Navigate fires — without Routes here the boundary
          would re-render Navigate forever (harness artifact). */}
      <Routes>
        <Route
          path={path}
          element={
            <RouteAccessBoundary route={route}>
              <div data-testid="panel-content">panel</div>
            </RouteAccessBoundary>
          }
        />
        <Route path="*" element={null} />
      </Routes>
      <LocationProbe />
    </MemoryRouter>
  );
  return seen;
}

describe('RouteAccessBoundary redirect target for missing tokens (Phase 0 follow-up)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    // Reset the in-memory expired-principal marker between tests.
    setToken('reset-marker-tmp');
    setToken(null);
  });

  it('sends an expired PATIENT session on the patient panel to /patient/login', async () => {
    sessionStorage.setItem(
      'auth_profile',
      JSON.stringify({ id: 42, username: 'patient-42', role: 'Patient' })
    );
    clearToken();
    expect(getExpiredPrincipalWasPatient()).toBe(true);

    const seen = renderAt('/patient', PATIENT_HOME_ROUTE);

    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/patient/login');
    });
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument();
    // Codex P2 (round 4): the hint is consumed once the target is selected —
    // later anonymous visits in this tab go to /login, not the patient form.
    expect(getExpiredPrincipalWasPatient()).toBe(false);
  });

  it('keeps /login for an expired STAFF session on the SHARED patient panel', async () => {
    // Codex round 3: Admin/Registrar/Doctor retain support access to
    // patient-home — a dead staff session there must NOT go to the patient
    // phone/OTP form.
    sessionStorage.setItem(
      'auth_profile',
      JSON.stringify({ id: 1, username: 'admin-1', role: 'Admin' })
    );
    clearToken();
    expect(getExpiredPrincipalWasPatient()).toBe(false);

    const seen = renderAt('/patient', PATIENT_HOME_ROUTE);

    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/login');
    });
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument();
  });

  it('keeps /login for an expired staff session on a staff route', async () => {
    sessionStorage.setItem(
      'auth_profile',
      JSON.stringify({ id: 2, username: 'registrar-2', role: 'Registrar' })
    );
    clearToken();

    const seen = renderAt('/registrar', REGISTRAR_HOME_ROUTE);

    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/login');
    });
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument();
  });

  it('keeps /login for anonymous visitors (no session ever cleared)', async () => {
    expect(getExpiredPrincipalWasPatient()).toBe(false);

    const seen = renderAt('/patient', PATIENT_HOME_ROUTE);

    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/login');
    });
  });
});
