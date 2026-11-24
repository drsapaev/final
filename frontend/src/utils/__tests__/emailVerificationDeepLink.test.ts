import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { extractEmailVerificationCredential, takeEmailVerificationCredential } from '../emailVerificationDeepLink';

const syntheticToken = `v1.${'s'.repeat(22)}.${'s'.repeat(22)}`;

describe('email verification deep link', () => {
  beforeEach(() => { window.history.replaceState(null, '', '/'); takeEmailVerificationCredential(); });
  afterEach(() => { takeEmailVerificationCredential(); vi.useRealTimers(); vi.restoreAllMocks(); window.history.replaceState(null, '', '/'); });

  it.each(['/verify-email', '/Verify-Email/', '/%76erify-email'])('strips and holds a fragment exactly once on %s', (path) => {
    window.history.replaceState(null, '', `${path}?lang=ru#token=${syntheticToken}`);
    extractEmailVerificationCredential();
    expect(window.location.hash).toBe('');
    expect(window.location.search).toBe('?lang=ru');
    expect(takeEmailVerificationCredential()).toBe(syntheticToken);
    expect(takeEmailVerificationCredential()).toBeNull();
  });

  it('strips but refuses query tokens and malformed or duplicated fragments', () => {
    window.history.replaceState(null, '', `/verify-email?token=${syntheticToken}&lang=ru#token=short`);
    extractEmailVerificationCredential();
    expect(window.location.search).toBe('?lang=ru');
    expect(window.location.hash).toBe('');
    expect(takeEmailVerificationCredential()).toBeNull();
    window.history.replaceState(null, '', `/verify-email#token=${syntheticToken}&token=${syntheticToken}`);
    extractEmailVerificationCredential();
    expect(window.location.hash).toBe('');
    expect(takeEmailVerificationCredential()).toBeNull();
  });

  it('expires an unconsumed in-memory credential', () => {
    vi.useFakeTimers();
    window.history.replaceState(null, '', `/verify-email#token=${syntheticToken}`);
    extractEmailVerificationCredential();
    vi.advanceTimersByTime(5 * 60 * 1000);
    expect(takeEmailVerificationCredential()).toBeNull();
  });

  it('does not store a token if clearing the history fails', () => {
    window.history.replaceState(null, '', `/verify-email#token=${syntheticToken}`);
    vi.spyOn(window.history, 'replaceState').mockImplementationOnce(() => { throw new Error('history unavailable'); });
    expect(extractEmailVerificationCredential).toThrow('history unavailable');
    expect(takeEmailVerificationCredential()).toBeNull();
  });

  it('extracts during the first startup module before telemetry initialization', () => {
    const main = readFileSync('src/main.tsx', 'utf8');
    expect(main.trimStart().startsWith('import \'./utils/emailVerificationBootstrap\';')).toBe(true);
    expect(main.indexOf('emailVerificationBootstrap')).toBeLessThan(main.indexOf('initSentry();'));
  });
});
