import { describe, expect, it } from 'vitest';

import {
  formatUzbekPhoneDisplay,
  isValidUzbekPhone,
  normalizeUzbekPhoneForApi
} from '../phoneUtils';

describe('phoneUtils', () => {
  it('normalizes a local Uzbek mobile number to canonical +998 format', () => {
    expect(normalizeUzbekPhoneForApi('901234567')).toBe('+998901234567');
    expect(formatUzbekPhoneDisplay('901234567')).toBe('+998 90 123 45 67');
    expect(isValidUzbekPhone('901234567')).toBe(true);
  });

  it('keeps an already canonical Uzbek phone number readable', () => {
    expect(normalizeUzbekPhoneForApi('+998 (90) 123-45-67')).toBe('+998901234567');
    expect(formatUzbekPhoneDisplay('+998 (90) 123-45-67')).toBe('+998 90 123 45 67');
    expect(isValidUzbekPhone('+998 (90) 123-45-67')).toBe(true);
  });

  it('rejects incomplete phone input', () => {
    expect(isValidUzbekPhone('12345')).toBe(false);
  });
});
