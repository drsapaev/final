import { describe, expect, it } from 'vitest';
import { hasRouteAccess, routeToRoles } from '../../constants/routes';

describe('RBAC route parity', () => {
  it('uses backend-aligned role set for registrar routes', () => {
    const roles = routeToRoles('/registrar');
    expect(roles).toEqual(['Admin', 'Registrar']);
  });

  it('exposes Patient role on patient panel route (P-001 fix)', () => {
    // P-001 fix: previously 'Patient' was excluded from patient-home.roles,
    // which caused every patient login to bounce to /forbidden because
    // homeForRoles:['patient'] resolved to /patient while the role guard
    // rejected the patient. Patient is now an explicit role on the route.
    const roles = routeToRoles('/patient');
    expect(roles).toEqual(['Admin', 'Registrar', 'Doctor', 'Patient']);
    expect(roles).toContain('Patient');
  });

  it('denies the deprecated Receptionist spelling on registrar routes (REC-3)', () => {
    // REC-3 (Receptionist deprecation): the receptionist -> registrar route
    // alias was removed. Registrar is the canonical front-desk role, and a
    // legacy 'Receptionist' profile must no longer reach registrar-family
    // routes. This is the E-3 proof that closed the deferred RoleGate
    // finding without widening RoleGate: route and page gates now agree.
    const profile = { role: 'Receptionist' };
    expect(hasRouteAccess(profile, '/registrar')).toBe(false);
    expect(hasRouteAccess(profile, '/registrar-panel')).toBe(false);
    expect(hasRouteAccess(profile, '/clinical/appointments')).toBe(false);
  });

  it('keeps the canonical Registrar spelling on registrar routes (REC-3)', () => {
    const profile = { role: 'Registrar' };
    expect(hasRouteAccess(profile, '/registrar')).toBe(true);
    expect(hasRouteAccess(profile, '/registrar-panel')).toBe(true);
    expect(hasRouteAccess(profile, '/clinical/appointments')).toBe(true);
  });

  it('keeps nurse compatibility through doctor alias', () => {
    const profile = { role: 'Nurse' };
    expect(hasRouteAccess(profile, '/clinical/scheduler')).toBe(true);
  });
});
