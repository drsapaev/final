import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const translationsSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/utils/labTranslations.js'), 'utf8'
);

const migratedFiles = [
  'AdminDashboard', 'UserExportManager', 'UserManagement', 'ServiceBatchEdit',
  'ServiceCatalog', 'QueueCabinetManagement', 'QueueProfilesManager',
  'DepartmentManagement', 'DynamicPricingManager', 'ReportsManager',
  'WebhookManager', 'SystemManagement', 'ActivationSystem', 'PatientModal',
  'AISettings', 'ServiceForm',
];

describe('Admin remaining STRAT#37 — i18n migration', () => {
  for (const name of migratedFiles) {
    const source = fs.readFileSync(
      path.join(ROOT, `components/admin/${name}.jsx`), 'utf8'
    );
    
    it(`${name} imports t from i18n adapter`, () => {
      expect(source).toContain("from '../../i18n/adapter'");
    });
    
    it(`${name} has no hardcoded Russian confirm/notify strings`, () => {
      expect(source).not.toMatch(/title: '[А-Яа-я]/);
      expect(source).not.toMatch(/confirmLabel: '[А-Яа-я]/);
      expect(source).not.toMatch(/cancelLabel: '[А-Яа-я]/);
    });
  }

  it('labTranslations has admin2.* namespace', () => {
    expect(translationsSource).toContain('admin2: {');
    expect(translationsSource).toContain('delete_confirm:');
    expect(translationsSource).toContain('stat_appointments_today:');
    expect(translationsSource).toContain('revoke_activation_title:');
  });
});
