import { describe, expect, it } from 'vitest';
import { useTranslation, t, tInterpolate, i18n } from '../adapter';

describe('i18n adapter (STRAT#29)', () => {
  describe('useTranslation hook', () => {
    it('returns t function and i18n instance', () => {
      const result = useTranslation();
      expect(result.t).toBeDefined();
      expect(typeof result.t).toBe('function');
      expect(result.i18n).toBeDefined();
      expect(result.ready).toBe(true);
    });

    it('t() returns Russian string for valid key', () => {
      const { t } = useTranslation();
      expect(t('common.save')).toBe('Сохранить');
      expect(t('common.cancel')).toBe('Отмена');
    });

    it('t() with params uses tInterpolate for {param} substitution', () => {
      const { t } = useTranslation();
      const result = t('confirm.delete_section_message', { name: 'Гемограмма' });
      expect(result).toContain('Гемограмма');
      expect(result).toContain('будет удалена');
    });

    it('t() returns key itself for missing translations', () => {
      const { t } = useTranslation();
      expect(t('nonexistent.key')).toBe('nonexistent.key');
    });
  });

  describe('i18n instance', () => {
    it('has language set to ru', () => {
      expect(i18n.language).toBe('ru');
      expect(i18n.languages).toContain('ru');
    });

    it('exists() returns true for valid keys', () => {
      expect(i18n.exists('common.save')).toBe(true);
      expect(i18n.exists('status.draft')).toBe(true);
    });

    it('exists() returns false for invalid keys', () => {
      expect(i18n.exists('nonexistent.key')).toBe(false);
    });

    it('i18n.t() works as standalone function', () => {
      expect(i18n.t('common.save')).toBe('Сохранить');
      expect(i18n.t('confirm.delete_section_message', { name: 'Test' })).toContain('Test');
    });

    it('changeLanguage is a no-op that returns the language', async () => {
      const result = await i18n.changeLanguage('en');
      expect(result).toBe('en');
      expect(i18n.language).toBe('ru');
    });
  });

  describe('raw exports', () => {
    it('exports t function', () => {
      expect(t('common.save')).toBe('Сохранить');
    });

    it('exports tInterpolate function', () => {
      const result = tInterpolate('confirm.delete_section_message', { name: 'Test' });
      expect(result).toContain('Test');
    });
  });

  describe('react-i18next API compatibility', () => {
    it('useTranslation returns { t, i18n, ready } — matches react-i18next signature', () => {
      const result = useTranslation();
      expect(Object.keys(result).sort()).toEqual(['i18n', 'ready', 't']);
    });

    it('t() accepts (key) and (key, params) — matches react-i18next signature', () => {
      const { t } = useTranslation();
      expect(t('common.save')).toBe('Сохранить');
      const result = t('confirm.delete_section_message', { name: 'Test' });
      expect(result).toContain('Test');
    });
  });
});
