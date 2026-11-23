/**
 * EMRTREAT-FE-001 (audit 3886, round 29) — fail-first unit regressions
 * for the canonical treatment-text selector.
 *
 * Pre-fix behavior: the EMR completeness indicator's «Лечение» row checked
 * ONLY `data.treatment`, while the visible TreatmentSection editor is
 * bound to `data.medications.text` (and the backend's canonical extraction
 * reads treatment → medications.text → plan.treatment). A doctor who
 * entered a genuine treatment plan in the editor still saw «Лечение»
 * listed as missing.
 */
import { describe, expect, it } from 'vitest';
import { emrTreatmentText } from '../emrCompletion';

describe('EMRTREAT-FE-001: emrTreatmentText counts the canonical treatment text', () => {
  it('reads the medications.text the visible editor is bound to', () => {
    expect(emrTreatmentText({ medications: { text: 'Амлодипин 5 мг 1 р/д', list: [] } }))
      .toBe('Амлодипин 5 мг 1 р/д');
  });

  it('prefers the narrative treatment field when both exist', () => {
    expect(emrTreatmentText({
      treatment: 'Госпитализация в кардиологию',
      medications: { text: 'Аспирин' },
    })).toBe('Госпитализация в кардиологию');
  });

  it('falls back to the legacy plan.treatment shape', () => {
    expect(emrTreatmentText({ plan: { treatment: 'Плановая операция' } }))
      .toBe('Плановая операция');
  });

  it('accepts the structured treatment shape ({main}) like other sections', () => {
    expect(emrTreatmentText({ treatment: { main: 'Терапия обострения' } }))
      .toBe('Терапия обострения');
  });

  it('treats whitespace-only and absent text as unfilled', () => {
    expect(emrTreatmentText({})).toBe('');
    expect(emrTreatmentText(null)).toBe('');
    expect(emrTreatmentText(undefined)).toBe('');
    expect(emrTreatmentText({ treatment: '   ' })).toBe('');
    expect(emrTreatmentText({ medications: { text: '  ', list: [] } })).toBe('');
    expect(emrTreatmentText({ medications: { list: [] } })).toBe('');
    expect(emrTreatmentText({ plan: { treatment: '' } })).toBe('');
  });
});
