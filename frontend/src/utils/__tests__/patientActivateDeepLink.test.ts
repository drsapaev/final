/**
 * Phase 0 follow-up (Codex P1): the activation fragment credential must be
 * extracted and stripped BEFORE telemetry (Sentry) initialization — the
 * scrubber redacts token-keyed fields, not URL-valued telemetry fields.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
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
});
