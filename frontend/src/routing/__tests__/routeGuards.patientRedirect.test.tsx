/**
 * Phase 0 follow-up (Codex P1, rounds 2-3): where does a missing token land?
 * The redirect target follows the EXPIRED PRINCIPAL, not the route — the
 * patient panel route is shared with support staff, so route metadata cannot
 * identify whose session died. An expired PATIENT lands on /patient/login
 * (the phone/OTP entry point); expired staff and anonymous visitors keep
 * /login — including staff whose session dies ON the shared patient panel.
 */
import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RouteAccessBoundary } from '../routeGuards';
import {
  clearToken,
  getExpiredPrincipalWasPatient,
  replaceAccessOnlySession,
  setToken,
} from '../../stores/auth';

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

function createJwt(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({
    sub: '42',
    exp: Math.floor(Date.now() / 1000) + expSecondsFromNow,
  }));
  return `${header}.${payload}.signature`;
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

  it('drops the stale hint when a public route mounts after an explicit logout', async () => {
    // Codex P2 (round 5): HeaderNew logout calls clearToken() then batches
    // navigate('/login') with the auth update — the protected boundary can
    // be unmounted BEFORE its missing-token effect runs, so the public
    // boundary's evaluation must drop the hint instead.
    sessionStorage.setItem(
      'auth_profile',
      JSON.stringify({ id: 42, username: 'patient-42', role: 'Patient' })
    );
    clearToken();
    expect(getExpiredPrincipalWasPatient()).toBe(true);

    const PUBLIC_LOGIN_ROUTE: BoundaryRoute = {
      id: 'login',
      group: 'public',
      auth: 'public',
      roles: [],
    };
    renderAt('/login', PUBLIC_LOGIN_ROUTE);

    await waitFor(() => {
      expect(getExpiredPrincipalWasPatient()).toBe(false);
    });
  });

  it('drops the hint when an already-mounted public boundary re-renders after a delayed 401', async () => {
    // Codex P2 (round 7): the patient browses a public page with a live
    // session; a business request returns 401 and the interceptor clears
    // the session. The mounted public boundary re-renders with an UNCHANGED
    // missingTokenRedirect (false) — the consumption must key on the
    // auth-state update, not on the boolean.
    replaceAccessOnlySession('patient-jwt', {
      id: 42,
      username: 'patient-42',
      role: 'Patient',
    } as never);

    const PUBLIC_ROUTE: BoundaryRoute = {
      id: 'some-public',
      group: 'public',
      auth: 'public',
      roles: [],
    };
    renderAt('/public-page', PUBLIC_ROUTE);
    await waitFor(() => {
      expect(screen.getByTestId('panel-content')).toBeInTheDocument();
    });

    clearToken();
    expect(getExpiredPrincipalWasPatient()).toBe(true);

    // The auth-state-driven re-render must consume the hint.
    await waitFor(() => {
      expect(getExpiredPrincipalWasPatient()).toBe(false);
    });
  });

  it('sends a patient session cleared while mounted to /patient/login via the snapshot', async () => {
    // Codex P2 (round 8): the boundary observes the clear through its
    // auth subscription — the redirect target must come from the notified
    // snapshot (flag carried atomically with the token-clear).
    replaceAccessOnlySession(createJwt(3600), {
      id: 42,
      username: 'patient-42',
      role: 'Patient',
    } as never);

    const seen = renderAt('/patient', PATIENT_HOME_ROUTE);
    // Live patient session: after the async session validation the panel
    // renders.
    await waitFor(() => {
      expect(screen.getByTestId('panel-content')).toBeInTheDocument();
    });

    // JWT dies mid-session: the interceptor-driven clearToken notifies
    // subscribers and the mounted boundary re-renders.
    clearToken();

    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/patient/login');
    });
  });

  it('does not reuse the consumed patient episode on a later protected visit (round 9)', async () => {
    replaceAccessOnlySession(createJwt(3600), {
      id: 42,
      username: 'patient-42',
      role: 'Patient',
    } as never);

    const ADMIN_ROUTE: BoundaryRoute = {
      id: 'admin',
      group: 'admin',
      auth: 'role-scoped',
      roles: ['Admin'],
      homeForRoles: ['admin'],
    };

    const PUBLIC_LOGIN_ROUTE: BoundaryRoute = {
      id: 'login',
      group: 'public',
      auth: 'public',
      roles: [],
    };
    const seen: string[] = [];
    const LocationProbe = () => {
      const { pathname } = useLocation();
      if (seen[seen.length - 1] !== pathname) {
        seen.push(pathname);
      }
      return null;
    };

    const routeSwitchController = { set: (_next: BoundaryRoute) => {} };

    function Harness() {
      const [route, setRoute] = useState<BoundaryRoute>(PUBLIC_LOGIN_ROUTE);
      routeSwitchController.set = (next: BoundaryRoute) => setRoute(next);
      return (
        <>
          <RouteAccessBoundary route={route}>
            <div data-testid="panel-content">panel</div>
          </RouteAccessBoundary>
          <LocationProbe />
        </>
      );
    }

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Harness />
      </MemoryRouter>
    );

    // Live patient session on the public route; the session dies (delayed
    // 401) — the episode is consumed on this public boundary render and the
    // global hint is dropped by the boundary's hygiene effect.
    clearToken();
    await waitFor(() => {
      expect(getExpiredPrincipalWasPatient()).toBe(false);
    });

    // Navigate to a protected staff route through the SAME boundary
    // instance (retained snapshot must not misdirect).
    routeSwitchController.set(ADMIN_ROUTE);

    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/login');
    });
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument();
  });

  it('re-arms after the redirect reaches the patient login (round 10)', async () => {
    // Codex P2 (round 10): protected-expiry → patient-login → staff-route
    // transition through ONE preserved boundary instance. Once the Navigate
    // reaches the public login route, the episode must end — a later
    // anonymous visit to a staff route keeps /login.
    replaceAccessOnlySession(createJwt(3600), {
      id: 42,
      username: 'patient-42',
      role: 'Patient',
    } as never);

    const routeMap: Record<string, BoundaryRoute> = {
      '/patient': PATIENT_HOME_ROUTE,
      '/patient/login': {
        id: 'patient-login',
        group: 'public',
        auth: 'public',
        roles: [],
      },
      '/admin': {
        id: 'admin',
        group: 'admin',
        auth: 'role-scoped',
        roles: ['Admin'],
        homeForRoles: ['admin'],
      },
      '/login': {
        id: 'login',
        group: 'public',
        auth: 'public',
        roles: [],
      },
    };
    const seen: string[] = [];
    const LocationProbe = () => {
      const { pathname } = useLocation();
      if (seen[seen.length - 1] !== pathname) {
        seen.push(pathname);
      }
      return null;
    };

    function Harness() {
      const location = useLocation();
      const navigate = useNavigate();
      const route = routeMap[location.pathname] ?? null;
      return (
        <>
          <RouteAccessBoundary route={route}>
            <div data-testid="panel-content">panel</div>
          </RouteAccessBoundary>
          <button data-testid="go-admin" onClick={() => navigate('/admin')}>admin</button>
          <LocationProbe />
        </>
      );
    }

    render(
      <MemoryRouter initialEntries={['/patient']}>
        <Harness />
      </MemoryRouter>
    );

    // Live patient session on /patient: the panel renders.
    await waitFor(() => {
      expect(screen.getByTestId('panel-content')).toBeInTheDocument();
    });

    // JWT dies mid-session: the frozen redirect fires to /patient/login —
    // the SAME boundary instance renders the public route afterwards.
    clearToken();
    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/patient/login');
    });

    // A later anonymous visit to a protected staff route keeps /login.
    fireEvent.click(screen.getByTestId('go-admin'));
    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/login');
    });
  });
});
