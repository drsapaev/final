import { describe, expect, it } from 'vitest';
import {
  isSetupAllowedPath,
  shouldRedirectFromSetup,
  shouldRedirectToSetup
} from '../setupRouting';

describe('setupRouting', () => {
  it('allows setup and health while deployment is uninitialized', () => {
    expect(isSetupAllowedPath('/setup')).toBe(true);
    expect(isSetupAllowedPath('/health')).toBe(true);
    expect(isSetupAllowedPath('/login')).toBe(false);
  });

  it('redirects regular app routes to setup before initialization', () => {
    expect(shouldRedirectToSetup('/', false)).toBe(true);
    expect(shouldRedirectToSetup('/login', false)).toBe(true);
    expect(shouldRedirectToSetup('/setup', false)).toBe(false);
  });

  it('redirects setup back to login after initialization', () => {
    expect(shouldRedirectFromSetup('/setup', true)).toBe(true);
    expect(shouldRedirectFromSetup('/login', true)).toBe(false);
  });
});
