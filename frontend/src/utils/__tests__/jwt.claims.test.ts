import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * AUTH-FE-001 (audit 3886, round 13) — fail-first.
 *
 * JWT payload — Base64URL: символы `-` и `_` легальны и встречаются в
 * валидных токенах (изолированное доказательство в ledger: payload
 * {exp, note:'>'} кодируется в base64url с `-`). «Сырой» atob reject-ит
 * их (InvalidCharacterError), и все три UI-читателя срока действия
 * деградировали молча:
 *   - getTokenExpiryMs → null: предупреждение об истечении skip-ается;
 *   - isTokenExpiringSoon → false: проактивный refresh skip-ается;
 *   - tokenManager.isTokenValid → TRUE из catch: fail-open на UI-уровне.
 *
 * Тесты ниже падают на до-фиксном коде (см. AUTH-FE-001 в
 * docs/audits/2026-11-05-qr-join-public-flow-source-review.md).
 */

import { decodeJwtClaims, numericClaim } from '../jwt';
import { getTokenExpiryMs } from '../../hooks/useSessionTimeoutWarning';
import { isTokenExpiringSoon } from '../../api/client';
import tokenManager from '../tokenManager';

function b64urlFromJson(value: unknown): string {
  const json = JSON.stringify(value);
  const bytes = new TextEncoder().encode(json);
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/** Синтетический JWT-подобный токен: header.payload.signature (без подписи — клиентский decode не является верификацией). */
function syntheticToken(claims: Record<string, unknown>): string {
  return `synthetic.${b64urlFromJson(claims)}.signature`;
}

describe('AUTH-FE-001: tolerant Base64URL JWT claim parsing', () => {
  it('decodes a payload whose base64url contains `-` (the ledger ">" proof)', () => {
    // {exp: 1730000000, note: '>'} → base64url содержит '-' (см. ledger:
    // Buffer(base64url) 'eyJleHAiOjE3MzAwMDAwMDAsIm5vdGUiOiI-In0').
    const token = syntheticToken({ exp: 1730000000, note: '>' });
    const claims = decodeJwtClaims(token);
    expect(claims).not.toBeNull();
    expect(claims?.note).toBe('>');
    expect(claims?.exp).toBe(1730000000);
  });

  it('getTokenExpiryMs returns the epoch for a Base64URL token (was null on atob throw)', () => {
    const token = syntheticToken({ exp: 1730000000, note: '>' });
    expect(getTokenExpiryMs(token)).toBe(1730000000000);
  });

  it('getTokenExpiryMs decodes UTF-8 (cyrillic) payloads', () => {
    const token = syntheticToken({ exp: 2000000000, sub: 'Доктор' });
    const claims = decodeJwtClaims(token);
    expect(claims?.sub).toBe('Доктор');
    expect(getTokenExpiryMs(token)).toBe(2000000000000);
  });

  it('isTokenExpiringSoon fires near expiry for a Base64URL token (was false on atob throw)', () => {
    const expiringSoon = Math.floor(Date.now() / 1000) + 60;
    const token = syntheticToken({ exp: expiringSoon, note: '>' });
    expect(isTokenExpiringSoon(token)).toBe(true);
  });

  it('isTokenExpiringSoon stays false far from expiry', () => {
    const far = Math.floor(Date.now() / 1000) + 3600;
    const token = syntheticToken({ exp: far, note: '>' });
    expect(isTokenExpiringSoon(token)).toBe(false);
  });

  it('isTokenExpiringSoon remains false for a non-JWT string (reactive 401 path is the authority)', () => {
    expect(isTokenExpiringSoon('opaque-backend-session-token')).toBe(false);
    expect(isTokenExpiringSoon('a.b')).toBe(false);
    // Отсутствие токена = «истекает скоро»: безопаснее триггерить refresh.
    expect(isTokenExpiringSoon('')).toBe(true);
  });

  describe('tokenManager.isTokenValid — fail-closed on decode failure', () => {
    beforeEach(() => {
      sessionStorage.clear();
      vi.spyOn(tokenManager, 'getAccessToken');
    });

    it('rejects an EXPIRED Base64URL token (was true from the catch branch)', () => {
      const expired = Math.floor(Date.now() / 1000) - 3600;
      const token = syntheticToken({ exp: expired, note: '>' });
      sessionStorage.setItem('auth_token', token);
      expect(tokenManager.isTokenValid()).toBe(false);
    });

    it('accepts a valid unexpired Base64URL token', () => {
      const valid = Math.floor(Date.now() / 1000) + 3600;
      const token = syntheticToken({ exp: valid, note: '>' });
      sessionStorage.setItem('auth_token', token);
      expect(tokenManager.isTokenValid()).toBe(true);
    });

    it('rejects a three-part token with a broken payload (fail-closed, was true)', () => {
      sessionStorage.setItem('auth_token', 'header.!!!not-base64!!!.signature');
      expect(tokenManager.isTokenValid()).toBe(false);
    });

    it('rejects a three-part token whose payload is not a JSON object', () => {
      sessionStorage.setItem('auth_token', syntheticTokenRaw('"just a string"'));
      expect(tokenManager.isTokenValid()).toBe(false);
    });

    it('still accepts a three-part token without a numeric exp (backend /me rejects)', () => {
      const token = syntheticToken({ sub: 'Доктор' });
      sessionStorage.setItem('auth_token', token);
      expect(tokenManager.isTokenValid()).toBe(true);
    });

    it('returns false without a token', () => {
      expect(tokenManager.isTokenValid()).toBe(false);
    });
  });

  it('numericClaim reads numeric exp and ignores non-numeric forms', () => {
    expect(numericClaim({ exp: 42 }, 'exp')).toBe(42);
    expect(numericClaim({ exp: '43' }, 'exp')).toBe(43);
    expect(numericClaim({ exp: 'soon' }, 'exp')).toBeNull();
    expect(numericClaim(null, 'exp')).toBeNull();
    expect(numericClaim({}, 'exp')).toBeNull();
  });
});

function syntheticTokenRaw(payloadSegment: string): string {
  const bytes = new TextEncoder().encode(payloadSegment);
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return `synthetic.${btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')}.signature`;
}
