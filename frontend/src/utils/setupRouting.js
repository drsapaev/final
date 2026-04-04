export function isSetupAllowedPath(pathname = '') {
  return pathname === '/setup' || pathname === '/health';
}

export function shouldRedirectToSetup(pathname = '', initialized = true) {
  return !initialized && !isSetupAllowedPath(pathname);
}

export function shouldRedirectFromSetup(pathname = '', initialized = true) {
  return initialized && pathname === '/setup';
}
