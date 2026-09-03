/**
 * M-1 (Manager deprecation) — frontend roles SSOT contract.
 *
 * Manager is a deprecated legacy/synthetic role (business decision
 * 2026-09-03): production holds exactly one legacy row (smoke_manager)
 * awaiting post-deploy ops deactivation; human Manager users = 0.
 *
 * Contract:
 *  - 'Manager' is NO LONGER an ADMIN_ROLES member (neither backend
 *    core/roles.py nor this frontend mirror) — a legacy Manager account
 *    must never be treated as administrative.
 *  - 'Manager' STAYS in the BackendRole vocabulary + isBackendRole +
 *    ROLE_LEVEL during the compatibility window so the surviving
 *    production row still type-checks on READ (mirrors the REC-1
 *    Receptionist compatibility rule). M-2 removes the vocabulary.
 */
import { describe, expect, it } from 'vitest';
import {
  ADMIN_ROLES,
  BackendRole,
  ROLE_LEVEL,
  isBackendRole,
  isAdminRole,
} from '../roles';

describe('M-1 Manager deprecation — roles SSOT', () => {
  it('Manager is not an ADMIN_ROLES member', () => {
    expect(ADMIN_ROLES).not.toContain('Manager');
    expect(isAdminRole('Manager')).toBe(false);
  });

  it('canonical admin roles are unaffected', () => {
    expect(ADMIN_ROLES).toContain('Admin');
    expect(ADMIN_ROLES).toContain('SuperAdmin');
    expect(isAdminRole('Admin')).toBe(true);
    expect(isAdminRole('SuperAdmin')).toBe(true);
  });

  it('Manager stays readable in the BackendRole vocabulary (compat window)', () => {
    // READ compatibility: the legacy production row (smoke_manager) must
    // still be recognized until the post-deploy ops deactivation + M-2.
    expect(isBackendRole('Manager')).toBe(true);
    expect(ROLE_LEVEL['Manager' as BackendRole]).toBe(8);
  });
});
