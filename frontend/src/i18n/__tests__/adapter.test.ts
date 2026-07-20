import { describe, expect, it } from 'vitest';
import { t as rawT, tInterpolate as rawTInterpolate, i18n } from '../useTranslation';

// react-i18next's t() has a typed-keys signature that requires options
// or a defaultValue. The adapter re-exports it directly, so we cast to
// a permissive signature for the test's call sites (which pass only a
// key). The runtime behavior is unchanged.
const t = rawT as unknown as (key: string) => string;
const tInterpolate = rawTInterpolate as unknown as (key: string, params: Record<string, unknown>) => string;
const i18nT = i18n.t as unknown as (key: string) => string;

/**
 * STRAT#49: Updated tests for react-i18next-backed adapter.
 *
 * Previously (STRAT#29) these tests tested the lightweight local adapter.
 * Now that react-i18next is installed, useTranslation() delegates to
 * react-i18next's own implementation (tested by their suite).
 * These tests focus on the raw t/tInterpolate exports and i18n instance.
 */

describe('i18n adapter (STRAT#29 + STRAT#49)', () => {
  describe('raw exports', () => {
    it('t() returns Russian string for valid key', () => {
      expect(t('common.save')).toBe('Сохранить');
      expect(t('common.cancel')).toBe('Отмена');
    });

    it('t() returns key itself for missing translations', () => {
      expect(t('nonexistent.key')).toBe('nonexistent.key');
    });

    it('tInterpolate() replaces {param} placeholders', () => {
      const result = tInterpolate('confirm.delete_section_message', { name: 'Гемограмма' });
      expect(result).toContain('Гемограмма');
      expect(result).toContain('будет удалена');
    });
  });

  describe('i18n instance (react-i18next)', () => {
    it('has language set to ru', () => {
      expect(i18n.language).toBe('ru');
    });

    it('exists() returns true for valid keys', () => {
      expect(i18n.exists('common.save')).toBe(true);
    });

    it('exists() returns false for invalid keys', () => {
      expect(i18n.exists('nonexistent.key')).toBe(false);
    });

    it('t() works as standalone function', () => {
      expect(i18nT('common.save')).toBe('Сохранить');
    });

    it('changeLanguage is available (react-i18next)', () => {
      expect(typeof i18n.changeLanguage).toBe('function');
    });
  });

  describe('react-i18next integration', () => {
    it('useTranslation is exported (delegated to react-i18next)', async () => {
      const mod = await import('../useTranslation');
      expect(mod.useTranslation).toBeDefined();
      expect(typeof mod.useTranslation).toBe('function');
    });

    it('i18n is initialized with ru language', () => {
      expect(i18n.isInitialized).toBe(true);
    });

    it('i18n has resources loaded', () => {
      const resource = i18n.getResource('ru', 'translation', 'common.save');
      expect(resource).toBe('Сохранить');
    });
  });
});
