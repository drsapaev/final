import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const adminPanelPath = path.resolve(__dirname, '../AdminPanel.jsx');
const routeRegistryPath = path.resolve(__dirname, '../../routing/routeRegistry.js');

const CONTEXTUAL_ROUTE_SECTION_MAP = {
  'benefit-settings': 'benefit-settings',
  'wizard-settings': 'wizard-settings',
  'payment-providers': 'payment-providers',
  'clinic-settings': 'clinic-settings',
  'queue-settings': 'queue-settings',
  'display-settings': 'display-settings',
  'ai-settings': 'ai-settings',
  security: 'security'
};

function readAdminPanel() {
  return fs.readFileSync(adminPanelPath, 'utf8');
}

function readRouteRegistry() {
  return fs.readFileSync(routeRegistryPath, 'utf8');
}

describe('AdminPanel route state contract', () => {
  it('keeps direct contextual routes mapped to their intended section params', () => {
    const source = readAdminPanel();

    expect(source).toContain('const ADMIN_ROUTE_SECTION_PARAMS = {');

    Object.entries(CONTEXTUAL_ROUTE_SECTION_MAP).forEach(([routeSection, expectedParam]) => {
      const key = /^[a-zA-Z_$][\w$]*$/.test(routeSection) ? routeSection : `'${routeSection}'`;
      expect(source).toContain(`${key}: '${expectedParam}'`);
    });

    expect(source).toContain('params.set(\'section\', canonicalSectionParam);');
    expect(source).toContain('navigate({');
    expect(source).toContain('pathname: location.pathname');
    expect(source).toContain('{ replace: true }');
  });

  it('keeps Telegram settings out of the broad AdminPanel switch', () => {
    const adminPanelSource = readAdminPanel();
    const routeRegistrySource = readRouteRegistry();

    expect(adminPanelSource).not.toContain("'telegram-settings': 'settings'");
    expect(adminPanelSource).not.toContain("case 'telegram-settings':");
    expect(adminPanelSource).not.toContain('return <TelegramSettings />;');
    expect(routeRegistrySource).toContain("id: 'admin-telegram-settings'");
    expect(routeRegistrySource).toContain("component: 'TelegramSettings'");
  });
});
