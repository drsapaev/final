import { describe, expect, it } from 'vitest';

import {
  DENTISTRY_SPECIALTIES,
  isDentistrySpecialty,
} from '../dentistrySpecialty';

describe('dentistry specialty helpers', () => {
  it('accepts all supported dentistry aliases including stomatology', () => {
    expect(DENTISTRY_SPECIALTIES).toContain('stomatology');
    expect(isDentistrySpecialty('dental')).toBe(true);
    expect(isDentistrySpecialty('dentist')).toBe(true);
    expect(isDentistrySpecialty('dentistry')).toBe(true);
    expect(isDentistrySpecialty('stomatology')).toBe(true);
    expect(isDentistrySpecialty(' STOMATOLOGY ')).toBe(true);
  });

  it('rejects non-dentistry specialties', () => {
    expect(isDentistrySpecialty('cardiology')).toBe(false);
    expect(isDentistrySpecialty('laboratory')).toBe(false);
    expect(isDentistrySpecialty('')).toBe(false);
    expect(isDentistrySpecialty(null)).toBe(false);
  });
});
