/**
 * Mapper tests for the two-stage 2FA enrollment login branch.
 *
 * Domain invariant (AUTHENTICATION_LAWS_FOR_AI.md ЗАКОН 2, extended):
 *   requires_2fa_setup === true ⇒  access_token MUST NOT be present,
 *                                  enrollment_token MUST be present,
 *                                  requires_2fa MUST be false.
 *
 * The mapper must surface backend contract violations loudly
 * (AuthInvariantViolationError) instead of letting them flow silently.
 */
import { describe, expect, it } from 'vitest';

import {
  parseLoginResponse,
  tryParseLoginResponse,
} from '../auth-mapper';
import type { LoginResponseRaw } from '../api';

const base: LoginResponseRaw = {
  requires_2fa: false,
} as unknown as LoginResponseRaw;

const enrollmentDto: LoginResponseRaw = {
  ...base,
  requires_2fa_setup: true,
  enrollment_token: 'enroll-token-abc',
  access_token: null,
  refresh_token: null,
  user: { id: 1, role: 'Admin' },
} as unknown as LoginResponseRaw;

describe('parseLoginResponse — two-stage enrollment branch', () => {
  it('maps a valid enrollment response to LoginRequires2FASetup', () => {
    const result = parseLoginResponse(enrollmentDto);
    expect(result.requires_2fa).toBe(false);
    if (result.requires_2fa_setup) {
      expect(result.enrollment_token).toBe('enroll-token-abc');
    } else {
      throw new Error('expected LoginRequires2FASetup variant');
    }
    const asRecord = result as unknown as Record<string, unknown>;
    expect(asRecord.access_token).toBeUndefined();
  });

  it('throws when enrollment response leaks an access_token', () => {
    const dto = { ...enrollmentDto, access_token: 'stolen-session' } as unknown as LoginResponseRaw;
    expect(() => parseLoginResponse(dto)).toThrow(/requires_2fa_setup=true together with access/);
  });

  it('throws when enrollment_token is missing', () => {
    const dto = { ...enrollmentDto, enrollment_token: null } as unknown as LoginResponseRaw;
    expect(() => parseLoginResponse(dto)).toThrow(/without enrollment_token/);
  });

  it('throws when both enrollment and challenge flags are set', () => {
    const dto = { ...enrollmentDto, requires_2fa: true } as unknown as LoginResponseRaw;
    expect(() => parseLoginResponse(dto)).toThrow(/mutually exclusive/);
  });

  it('tryParseLoginResponse returns failure payload instead of throwing', () => {
    const bad = { ...enrollmentDto, access_token: 'x' } as unknown as LoginResponseRaw;
    const parsed = tryParseLoginResponse(bad);
    expect(parsed.ok).toBe(false);
  });
});

describe('parseLoginResponse — existing branches regression', () => {
  it('challenge branch still maps pending_2fa_token', () => {
    const dto = {
      requires_2fa: true,
      pending_2fa_token: 'pending-token',
      two_factor_method: 'totp',
    } as unknown as LoginResponseRaw;
    const result = parseLoginResponse(dto);
    expect(result.requires_2fa).toBe(true);
  });

  it('plain success branch still maps tokens', () => {
    const dto = {
      requires_2fa: false,
      access_token: 'at',
      refresh_token: 'rt',
      token_type: 'bearer',
      expires_in: 1800,
      user: { id: 2 },
    } as unknown as LoginResponseRaw;
    const result = parseLoginResponse(dto);
    expect(result.requires_2fa).toBe(false);
    const asRecord = result as unknown as Record<string, unknown>;
    expect(asRecord.requires_2fa_setup).not.toBe(true);
    expect(asRecord.enrollment_token).toBeUndefined();
  });
});
