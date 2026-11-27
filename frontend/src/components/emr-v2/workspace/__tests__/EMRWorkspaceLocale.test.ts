import { describe, expect, it } from 'vitest';
import en from '@/i18n/locales/en';
import kk from '@/i18n/locales/kk';
import ru from '@/i18n/locales/ru';
import uzCyrl from '@/i18n/locales/uz-Cyrl';
import uzLatn from '@/i18n/locales/uz-Latn';

const locales = { ru, en, kk, uzLatn, uzCyrl };
const workspaceKeys = [
  'patient_age',
  'specialty',
  'specialty_general',
  'specialty_cardiology',
  'specialty_dermatology',
  'specialty_dentistry',
  'specialty_lab',
  'initial_visit',
  'repeat_visit',
  'new_complaint_toggle',
  'more_actions',
] as const;

describe('EMR workspace M15 locale labels', () => {
  it.each(Object.entries(locales))('has complete labels for %s', (_locale, messages) => {
    for (const key of workspaceKeys) {
      expect(messages.emr_workspace[key], `${_locale}.${key}`).toBeTruthy();
    }
  });
});
