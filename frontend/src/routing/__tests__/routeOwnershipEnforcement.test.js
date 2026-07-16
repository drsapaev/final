import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

function read(relativePath) {
  return fs.readFileSync(path.resolve(process.cwd(), relativePath), 'utf8');
}

describe('routing anti-regression enforcement', () => {
  it('keeps legacy consumers free from hand-maintained route tables', () => {
    const routeRegistry = read('src/routing/routeRegistry.js');

    expect(read('src/components/layout/Nav.jsx')).not.toContain('const routes = [');
    expect(read('src/constants/routes.ts')).not.toContain('const routeMap =');
    expect(routeRegistry).not.toContain('component: \'AdminPanel\'');
  });

  it('uses the routing subsystem as the route source of truth', () => {
    expect(read('src/App.jsx')).toContain('from \'./routing/routeRegistry.js\'');
    expect(read('src/App.jsx')).toContain('ROUTE_REGISTRY.map');
    expect(read('src/components/layout/Nav.jsx')).toContain('getVisibleRoutesForShell');
  });
});
