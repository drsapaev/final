import { describe, expect, it } from 'vitest';
import { assertMedicalAiSafety, hasMedicalAiSafety } from '../aiSafety';

describe('medical AI safety envelope', () => {
  it.each([
    undefined, null, [], {}, { requires_doctor_confirmation: true },
    { ai_safety_meta: null }, { ai_safety_meta: [] },
    { ai_safety_meta: { requires_doctor_confirmation: false } },
    { ai_safety_meta: { requires_doctor_confirmation: 1 } },
    { ai_safety_meta: { requires_doctor_confirmation: 'true' } },
  ])('rejects an absent or malformed marker: %j', (value) => {
    expect(hasMedicalAiSafety(value)).toBe(false);
    expect(() => assertMedicalAiSafety(value)).toThrow();
  });

  it('accepts only the explicit nested boolean true', () => {
    const result = { ai_safety_meta: { requires_doctor_confirmation: true } };
    expect(hasMedicalAiSafety(result)).toBe(true);
    expect(() => assertMedicalAiSafety(result)).not.toThrow();
  });
});
