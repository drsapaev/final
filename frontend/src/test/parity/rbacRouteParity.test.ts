import { describe, expect, it } from 'vitest';
import { hasRouteAccess, routeToRoles } from '../../constants/routes';
import { SIDEBAR_PRESETS } from '../../routing/routeRegistry';

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

  it('drops the nurse -> doctor alias (N-3 retirement)', () => {
    // N-3: Nurse had 0 stored rows (production census 2026-09-05) and no
    // shipped UI surface; the routing alias was the last reachability
    // grant, so the spelling lands on deny like any retired role —
    // parity with the backend enum closure.
    const profile = { role: 'Nurse' };
    expect(hasRouteAccess(profile, '/clinical/scheduler')).toBe(false);
  });

  it('pins the canonical trio on the appointments route (P-014 TIGHTEN)', () => {
    // P-014 TIGHTEN: /clinical/appointments route-level roles collapsed back to
    // the canonical Admin/Doctor/Registrar trio. This matches the page RoleGate
    // (Appointments.tsx), the clinical-scheduler route above, and the backend
    // require_roles contract. The historical widening to Cashier/Lab/cardio/
    // derma/dentist was decorative: the backend list endpoint 403-rejects those
    // roles (doctor-family scoping; the page never sends doctor_id), so the
    // widened route registry only exposed dead UI reachability and /forbidden
    // landings.
    expect(routeToRoles('/clinical/appointments')).toEqual(['Admin', 'Doctor', 'Registrar']);
  });

  it('keeps the scheduler route on the same canonical trio (P-014 pin)', () => {
    // Scheduler and Appointments are one access surface (shared nav group,
    // shared backend require_roles) — pin both so a future widening cannot
    // diverge one from the other silently.
    expect(routeToRoles('/clinical/scheduler')).toEqual(['Admin', 'Doctor', 'Registrar']);
  });

  it('allows each trio role on the appointments route (P-014 pin)', () => {
    for (const role of ['Admin', 'Doctor', 'Registrar']) {
      expect(hasRouteAccess({ role }, '/clinical/appointments')).toBe(true);
    }
  });

  it('denies the historically widened non-canonical roles on appointments (P-014 TIGHTEN)', () => {
    // These five roles were granted route-level entry by the decorative
    // widening but were always 403-rejected by the backend list endpoint.
    // They must stay denied at the route layer so no dead entry points render.
    for (const role of ['Cashier', 'Lab', 'cardio', 'derma', 'dentist']) {
      expect(hasRouteAccess({ role }, '/clinical/appointments')).toBe(false);
      expect(hasRouteAccess({ role }, '/clinical/scheduler')).toBe(false);
    }
  });

  it('keeps the Cashier payment surface reachable (P-014 preservation pin)', () => {
    // Legitimate outlier preserved: Cashier's payment-facing surfaces are
    // /cashier (home) and the backend pending-payments feed
    // (APPOINTMENT_PENDING_PAYMENT_ROLES = {Admin, Registrar, Cashier}) —
    // neither flows through the shared appointments screen.
    expect(hasRouteAccess({ role: 'Cashier' }, '/cashier')).toBe(true);
    expect(routeToRoles('/cashier')).toContain('Cashier');
  });

  it('removes the appointments dead link from the cashier sidebar preset (P-014 TIGHTEN)', () => {
    // Non-admin presets are NOT access-filtered by getRouteChromeState (only
    // the admin preset is), so a preset item pointing at a route the role can
    // no longer access would render as a permanent dead link landing on
    // /forbidden. The cashier preset must therefore carry only the cashier
    // home item after the route-level tighten.
    const cashierItems = SIDEBAR_PRESETS.cashier.items.map((item) => item.id);
    expect(cashierItems).toEqual(['cashier-home']);
    expect(cashierItems).not.toContain('clinical-appointments');
  });
});
