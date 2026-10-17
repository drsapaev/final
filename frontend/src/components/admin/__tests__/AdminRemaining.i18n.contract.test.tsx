import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
import ruLocale from '../../../i18n/locales/ru';
import uzLatnLocale from '../../../i18n/locales/uz-Latn';
import uzCyrlLocale from '../../../i18n/locales/uz-Cyrl';
import enLocale from '../../../i18n/locales/en';
import kkLocale from '../../../i18n/locales/kk';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const translationsSource = fs.readFileSync(
  path.join(ROOT, 'i18n/locales/ru.ts'), 'utf8'
);

const migratedFiles = [
  'AdminDashboard', 'UserExportManager', 'UserManagement', 'ServiceBatchEdit',
  'ServiceCatalog', 'QueueCabinetManagement', 'QueueProfilesManager',
  'DepartmentManagement', 'DynamicPricingManager', 'ReportsManager',
  'WebhookManager', 'SystemManagement', 'ActivationSystem', 'PatientModal',
  'AISettings', 'ServiceForm',
  'PublicSiteMediaManager',
];

describe('Admin remaining STRAT#37 — i18n migration', () => {
  for (const name of migratedFiles) {
    const source = fs.readFileSync(
      path.join(ROOT, `components/admin/${name}.tsx`), 'utf8'
    );

    it(`${name} imports t from i18n adapter`, () => {
      expect(source).toContain('from \'../../i18n/useTranslation\'');
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

  it('PublicSiteMediaManager copy is complete in all five locales', () => {
    const locales = {
      ru: ruLocale.publicSiteMedia,
      'uz-Latn': uzLatnLocale.publicSiteMedia,
      'uz-Cyrl': uzCyrlLocale.publicSiteMedia,
      en: enLocale.publicSiteMedia,
      kk: kkLocale.publicSiteMedia,
    };
    const expectedKeys = Object.keys(locales.ru).sort();

    for (const [locale, messages] of Object.entries(locales)) {
      expect(Object.keys(messages).sort(), `${locale} has a different publicSiteMedia key set`).toEqual(expectedKeys);
      for (const [key, value] of Object.entries(messages)) {
        expect(typeof value, `${locale}.publicSiteMedia.${key} must be text`).toBe('string');
        expect(value.trim(), `${locale}.publicSiteMedia.${key} must not be empty`).not.toBe('');
      }
    }
  });
});
