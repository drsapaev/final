/**
 * Phase 0 follow-up (Codex P1): the activation fragment credential must be
 * extracted and stripped BEFORE telemetry (Sentry) initialization — the
 * scrubber redacts token-keyed fields, not URL-valued telemetry fields.
 *
 * Owner round-12 P1: the legacy ?token= query form (links already handed
 * out within the 72h TTL) must be stripped BEFORE telemetry init too — the
 * query component survives in window.location until the page effect, i.e.
 * past initSentry().
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  extractPatientActivationCredential,
  extractPatientActivationFragment,
  takePatientActivationFragmentToken,
} from '../patientActivateDeepLink';

describe('patientActivateDeepLink (Phase 0 follow-up)', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/');
  });

  afterEach(() => {
    // Drain the one-shot slot so tests never leak a pending credential.
    takePatientActivationFragmentToken();
    window.history.replaceState(null, '', '/');
  });

  it('stashes the fragment token and strips the fragment on the activate route', () => {
    const token = 'a'.repeat(43);
    window.history.replaceState(null, '', `/patient/activate#token=${token}`);

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBe(token);
    expect(window.location.hash).toBe('');
    // One-shot by design.
    expect(takePatientActivationFragmentToken()).toBeNull();
  });

  it('keeps unrelated query params while stripping the fragment', () => {
    const token = 'b'.repeat(43);
    window.history.replaceState(null, '', `/patient/activate?lang=ru#token=${token}`);

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBe(token);
    expect(window.location.search).toBe('?lang=ru');
    expect(window.location.hash).toBe('');
  });

  it('strips the fragment on the trailing-slash activate route too', () => {
    // Codex P1 (round 3): /patient/activate/ is served by the catch-all
    // rewrite and accepted by React Router — the credential must still be
    // stripped BEFORE telemetry init.
    const token = 'd'.repeat(43);
    window.history.replaceState(null, '', `/patient/activate/#token=${token}`);

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBe(token);
    expect(window.location.hash).toBe('');
    expect(window.location.pathname).toBe('/patient/activate/');
  });

  it('strips the fragment on case-insensitive route matches too', () => {
    // Codex P1 (round 6): React Router matches without caseSensitive, so
    // /Patient/Activate reaches the same page — the pre-telemetry strip
    // must accept that casing as well.
    const token = 'e'.repeat(43);
    window.history.replaceState(null, '', `/Patient/Activate#token=${token}`);

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBe(token);
    expect(window.location.hash).toBe('');
  });

  it('decodes percent-encoded activation paths before matching (round 11)', () => {
    // Codex P1 (round 11): React Router decodes the pathname before
    // matching, so /patient/%61ctivate reaches the activation page while
    // window.location.pathname stays encoded — the pre-telemetry strip
    // must decode before comparing.
    const token = 'f'.repeat(43);
    window.history.replaceState(null, '', `/patient/%61ctivate#token=${token}`);

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBe(token);
    expect(window.location.hash).toBe('');
  });

  it('is a no-op for a malformed percent-encoded path', () => {
    window.history.replaceState(null, '', '/patient/%E0%A4%A#token=abc');

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBeNull();
  });

  it('is a no-op on other routes even when a token-shaped fragment is present', () => {
    const token = 'c'.repeat(43);
    window.history.replaceState(null, '', `/some/page#token=${token}`);

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBeNull();
    expect(window.location.hash).toBe(`#token=${token}`);
  });

  it('is a no-op when the fragment carries no token value', () => {
    window.history.replaceState(null, '', '/patient/activate#section-2');

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBeNull();
    expect(window.location.hash).toBe('#section-2');
  });

  it('does not confuse similarly named fragment keys with the credential', () => {
    window.history.replaceState(null, '', '/patient/activate#payment_token=xyz');

    extractPatientActivationFragment();

    expect(takePatientActivationFragmentToken()).toBeNull();
  });

  // Owner round-12 P1: the legacy ?token= query form survives in
  // window.location until the PatientActivatePage effect — i.e. past
  // initSentry(). The bootstrap entry point (main.tsx) must strip it too.
  describe('legacy ?token= query (extractPatientActivationCredential)', () => {
    it('stashes the legacy query token and strips it before telemetry init', () => {
      const token = 'g'.repeat(43);
      window.history.replaceState(null, '', `/patient/activate?token=${token}&lang=ru`);

      extractPatientActivationCredential();

      expect(takePatientActivationFragmentToken()).toBe(token);
      expect(window.location.search).toBe('?lang=ru');
      expect(window.location.search).not.toContain(token);
      expect(window.location.pathname).toBe('/patient/activate');
    });

    it('preserves unrelated query params verbatim (order and encoding)', () => {
      const token = 'l'.repeat(43);
      window.history.replaceState(null, '', `/patient/activate?a=1&token=${token}&b=%D1%80%D1%83`);

      extractPatientActivationCredential();

      expect(window.location.search).toBe('?a=1&b=%D1%80%D1%83');
      expect(window.location.search).not.toContain(token);
    });

    it('prefers the fragment token when both forms are present, strips the query either way', () => {
      const fragmentToken = 'i'.repeat(43);
      const queryToken = 'h'.repeat(43);
      window.history.replaceState(null, '', `/patient/activate?token=${queryToken}#token=${fragmentToken}`);

      extractPatientActivationCredential();

      expect(takePatientActivationFragmentToken()).toBe(fragmentToken);
      expect(window.location.search).toBe('');
      expect(window.location.hash).toBe('');
      expect(window.location.href).not.toContain(queryToken);
    });

    it('strips the legacy query token on trailing-slash, case-insensitive and percent-encoded route forms', () => {
      // Rounds 3/6/11 parity: every pathname form the router accepts must
      // be stripped BEFORE telemetry init for the query handout form too.
      for (const pathname of ['/patient/activate/', '/Patient/Activate', '/patient/%61ctivate']) {
        const token = 'j'.repeat(43);
        window.history.replaceState(null, '', `${pathname}?token=${token}&x=1`);

        extractPatientActivationCredential();

        expect(window.location.search).toBe('?x=1');
        expect(window.location.search).not.toContain(token);
        expect(takePatientActivationFragmentToken()).toBe(token);
      }
    });

    it('strips a percent-encoded token param name (URLSearchParams decodes it)', () => {
      const token = 'n'.repeat(43);
      window.history.replaceState(null, '', `/patient/activate?%74oken=${token}&x=1`);

      extractPatientActivationCredential();

      expect(window.location.search).toBe('?x=1');
      expect(takePatientActivationFragmentToken()).toBe(token);
    });

    it('keeps an unrelated hash while stripping the legacy query token', () => {
      const token = 'k'.repeat(43);
      window.history.replaceState(null, '', `/patient/activate?token=${token}#section`);

      extractPatientActivationCredential();

      expect(takePatientActivationFragmentToken()).toBe(token);
      expect(window.location.search).toBe('');
      expect(window.location.hash).toBe('#section');
    });

    it('is a no-op for an empty token value (no credential to strip)', () => {
      window.history.replaceState(null, '', '/patient/activate?token=');

      extractPatientActivationCredential();

      expect(takePatientActivationFragmentToken()).toBeNull();
      expect(window.location.search).toBe('?token=');
    });

    it('is a no-op on other routes even with a token-shaped query', () => {
      const token = 'm'.repeat(43);
      window.history.replaceState(null, '', `/some/page?token=${token}`);

      extractPatientActivationCredential();

      expect(takePatientActivationFragmentToken()).toBeNull();
      expect(window.location.search).toBe(`?token=${token}`);
    });
  });
});
