import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const files = {
  AdminAppointments: 'components/admin/AdminAppointments.jsx',
  AdminDoctors: 'components/admin/AdminDoctors.jsx',
  AdminFinanceOverview: 'components/admin/AdminFinanceOverview.jsx',
  AdminPatients: 'components/admin/AdminPatients.jsx',
};

const translationsSource = fs.readFileSync(
  path.join(ROOT, 'i18n/locales/ru.js'), 'utf8'
);

describe('Admin components STRAT#36 — i18n migration', () => {
  for (const [name, file] of Object.entries(files)) {
    const source = fs.readFileSync(path.join(ROOT, file), 'utf8');
    
    it(`${name} imports t from i18n adapter`, () => {
      expect(source).toContain("from '../../i18n/useTranslation'");
    });
    
    it(`${name} uses t() for confirm dialog`, () => {
      expect(source).toContain("t('admin.");
    });
  }

  it('labTranslations has admin.* namespace', () => {
    expect(translationsSource).toContain('admin: {');
    expect(translationsSource).toContain('delete_appointment_title:');
    expect(translationsSource).toContain('deactivate_doctor_title:');
    expect(translationsSource).toContain('delete_transaction_title:');
    expect(translationsSource).toContain('delete_patient_title:');
  });

  it('does not contain hardcoded Russian strings in confirm dialogs', () => {
    for (const file of Object.values(files)) {
      const source = fs.readFileSync(path.join(ROOT, file), 'utf8');
      expect(source).not.toContain("title: 'Удаление");
      expect(source).not.toContain("title: 'Деактивация");
      expect(source).not.toContain("confirmLabel: 'Удалить'");
      expect(source).not.toContain("confirmLabel: 'Деактивировать'");
      expect(source).not.toContain("cancelLabel: 'Отмена'");
    }
  });
});
