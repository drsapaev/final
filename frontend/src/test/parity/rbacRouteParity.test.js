import { describe, expect, it } from 'vitest';
import { hasRouteAccess, routeToRoles } from '../../constants/routes';

describe('RBAC route parity', () => {
  it('uses backend-aligned role set for registrar routes', () => {
    const roles = routeToRoles('/registrar-panel');
    expect(roles).toEqual(['Admin', 'Registrar']);
  });

  it('does not expose frontend-only Patient role on patient panel route', () => {
    const roles = routeToRoles('/patient-panel');
    expect(roles).toEqual(['Admin', 'Registrar', 'Doctor']);
    expect(roles).not.toContain('Patient');
  });

  it('keeps receptionist compatibility through registrar alias', () => {
    const profile = { role: 'Receptionist' };
    expect(hasRouteAccess(profile, '/registrar-panel')).toBe(true);
    expect(hasRouteAccess(profile, '/appointments')).toBe(true);
  });

  it('keeps nurse compatibility through doctor alias', () => {
    const profile = { role: 'Nurse' };
    expect(hasRouteAccess(profile, '/scheduler')).toBe(true);
  });
});
