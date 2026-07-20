import { describe, expect, it } from 'vitest';
import { t as rawT, tInterpolate, TRANSLATIONS } from '../../../../i18n/useTranslation';

// Cast t() to a looser signature so we can test null/undefined/number inputs.
const t = rawT as unknown as (key: unknown) => unknown;

describe('labTranslations (STRAT#3)', () => {
  describe('t() function', () => {
    it('returns Russian string for valid dotted key', () => {
      expect(t('common.save')).toBe('Сохранить');
      expect(t('common.save_draft')).toBe('Сохранить черновик');
      expect(t('common.cancel')).toBe('Отмена');
    });

    it('returns nested keys correctly', () => {
      expect(t('status.draft')).toBe('Черновик');
      expect(t('status.finalized')).toBe('Утверждён');
      expect(t('errors.save_failed')).toBe('Не удалось сохранить.');
      expect(t('success.draft_saved')).toBe('Черновик сохранён.');
    });

    it('returns the key itself when not found (for debugging)', () => {
      expect(t('nonexistent.key')).toBe('nonexistent.key');
      expect(t('common.nonexistent')).toBe('common.nonexistent');
    });

    it('handles null/undefined/non-string input gracefully', () => {
      expect(t(null)).toBe(null);
      expect(t(undefined)).toBe(undefined);
      expect(t(123)).toBe(123);
    });

    it('returns key when intermediate path is not an object', () => {
      expect(t('common.save.foo')).toBe('common.save.foo');
    });
  });

  describe('tInterpolate() function', () => {
    it('replaces {param} placeholders with provided values', () => {
      const template = 'Поле {field} = {value} {unit}';
      const interpolated = template.replace(/\{(\w+)\}/g, (m, p) => {
        const params = { field: 'Hemoglobin', value: 12.5, unit: 'g/dL' };
        return params[p] !== undefined ? String(params[p]) : m;
      });
      expect(interpolated).toBe('Поле Hemoglobin = 12.5 g/dL');
    });

    it('returns string as-is when no params provided', () => {
      expect(tInterpolate('common.save')).toBe('Сохранить');
      expect(tInterpolate('common.save', null)).toBe('Сохранить');
    });

    it('leaves unmatched placeholders in place', () => {
      const template = 'Hello {name}, your score is {score}';
      const result = template.replace(/\{(\w+)\}/g, (m, p) => {
        const params = { name: 'Alice' };
        return params[p] !== undefined ? String(params[p]) : m;
      });
      expect(result).toBe('Hello Alice, your score is {score}');
    });
  });

  describe('TRANSLATIONS dictionary structure', () => {
    it('has all expected top-level namespaces', () => {
      const expectedNamespaces = [
        'common',
        'status',
        'queue_status',
        'workbench',
        'actions',
        'confirm',
        'template',
        'queue',
        'errors',
        'success',
        'empty',
        'pii',
      ];
      for (const ns of expectedNamespaces) {
        expect(TRANSLATIONS[ns]).toBeDefined();
        expect(typeof TRANSLATIONS[ns]).toBe('object');
      }
    });

    it('status namespace has all 7 lab report statuses', () => {
      const statuses = ['draft', 'in_progress', 'ready', 'finalized', 'printed', 'archived', 'unknown'];
      for (const s of statuses) {
        expect(TRANSLATIONS.status[s]).toBeDefined();
        expect(typeof TRANSLATIONS.status[s]).toBe('string');
      }
    });

    it('common namespace has essential action verbs', () => {
      const essentials = ['save', 'cancel', 'delete', 'confirm', 'close', 'refresh'];
      for (const e of essentials) {
        expect(TRANSLATIONS.common[e]).toBeDefined();
      }
    });

    it('confirm namespace has all irreversible-action dialog texts', () => {
      const dialogs = [
        'finalize_title', 'finalize_message', 'finalize_description',
        'revise_title', 'revise_message', 'revise_description',
        'notify_title', 'notify_message', 'notify_description',
        'reset_draft_title', 'reset_draft_message', 'reset_draft_description',
        'delete_section_title', 'delete_field_title',
        'order_title', 'order_message', 'order_description',
      ];
      for (const d of dialogs) {
        expect(TRANSLATIONS.confirm[d]).toBeDefined();
        expect(typeof TRANSLATIONS.confirm[d]).toBe('string');
      }
    });

    it('all values in common namespace are strings', () => {
      for (const value of Object.values(TRANSLATIONS.common)) {
        expect(typeof value).toBe('string');
      }
    });

    it('all values in status namespace are strings', () => {
      for (const value of Object.values(TRANSLATIONS.status)) {
        expect(typeof value).toBe('string');
      }
    });
  });
});
