import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { scrubPIIFromObject } from '../../services/sentry';
import {
  clearPasswordResetCredential,
  extractPasswordResetCredential,
  getPasswordResetCredential,
} from '../passwordResetDeepLink';

afterEach(() => {
  clearPasswordResetCredential();
  vi.restoreAllMocks();
  window.history.replaceState(null, '', '/');
});

describe('password reset link extraction', () => {
  it.each([
    '/reset-password#token=SYNTHETIC_capability-123',
    '/RESET-password/?%74oken=SYNTHETIC_capability-123',
  ])('captures and removes a canonical or legacy capability: %s', (url) => {
    window.history.replaceState(null, '', url);
    expect(extractPasswordResetCredential()).toBe(true);
    expect(getPasswordResetCredential()).toBe('SYNTHETIC_capability-123');
    expect(window.location.href).not.toContain('SYNTHETIC_capability-123');
    expect(extractPasswordResetCredential()).toBe(false);
    expect(getPasswordResetCredential()).toBe('SYNTHETIC_capability-123');
  });

  it('fails closed on duplicates across query and fragment and preserves unrelated values', () => {
    window.history.replaceState(null, '', '/reset-password?view=one&token=FIRST#%74oken=SECOND&section=profile');
    expect(extractPasswordResetCredential()).toBe(true);
    expect(getPasswordResetCredential()).toBeNull();
    expect(window.location.search).toBe('?view=one');
    expect(window.location.hash).toBe('#section=profile');
  });

  it('removes token-like parameters but does not accept them as credentials', () => {
    window.history.replaceState(null, '', '/reset-password?access_token=SYNTHETIC&next=login');
    expect(extractPasswordResetCredential()).toBe(true);
    expect(getPasswordResetCredential()).toBeNull();
    expect(window.location.search).toBe('?next=login');
  });

  it('clears any previously captured credential if address rewriting fails', () => {
    window.history.replaceState(null, '', '/reset-password#token=FIRST');
    extractPasswordResetCredential();
    window.history.replaceState(null, '', '/reset-password#token=SECOND');
    vi.spyOn(window.history, 'replaceState').mockImplementation(() => { throw new Error('unavailable'); });
    expect(() => extractPasswordResetCredential()).toThrow();
    expect(getPasswordResetCredential()).toBeNull();
  });

  it('bootstraps before application and telemetry imports', () => {
    const main = readFileSync(resolve(process.cwd(), 'src/main.tsx'), 'utf8');
    const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');
    expect(main.indexOf("import './utils/passwordResetBootstrap';")).toBeLessThan(main.indexOf("import React from 'react';"));
    expect(main.indexOf('passwordResetBootstrap')).toBeLessThan(main.indexOf('initSentry();'));
    expect(html.indexOf('<meta name="referrer" content="no-referrer"')).toBeLessThan(html.indexOf('<link '));
  });

  it('redacts the reset header in telemetry objects', () => {
    const event = { request: { headers: { 'X-Reset-Token': 'SYNTHETIC_CAPABILITY' } } };
    expect(JSON.stringify(scrubPIIFromObject(event))).not.toContain('SYNTHETIC_CAPABILITY');
  });
});
