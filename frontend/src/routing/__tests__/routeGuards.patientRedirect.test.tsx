/**
 * Phase 0 follow-up (Codex P1): where does a missing token land?
 * An expired access-only PATIENT session viewed on the patient panel must
 * be redirected to /patient/login (the phone/OTP entry point), not to the
 * staff login screen; staff routes keep /login.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { RouteAccessBoundary } from '../routeGuards';

vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'ru',
    setLanguage: vi.fn(),
    availableLanguages: [{ code: 'ru', name: 'Русский', flag: 'RU' }],
    t: (key: string) => key,
  }),
}));

type BoundaryRoute = NonNullable<Parameters<typeof RouteAccessBoundary>[0]['route']>;

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
  it('sends a missing/expired token on the patient panel to /patient/login', async () => {
    const seen = renderAt('/patient', PATIENT_HOME_ROUTE);

    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/patient/login');
    });
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument();
  });

  it('keeps the staff /login target for staff routes', async () => {
    const seen = renderAt('/registrar', REGISTRAR_HOME_ROUTE);

    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe('/login');
    });
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument();
  });
});
