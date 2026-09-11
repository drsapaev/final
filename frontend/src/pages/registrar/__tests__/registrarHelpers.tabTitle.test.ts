/**
 * RQ-20 (срез RQ-20.a): unit contract for resolveRegistrarTabLabel —
 * the shared title resolution for the registrar worklist header and the
 * breadcrumb department crumb.
 *
 * Pins the plan §RQ-20 result "произвольный профиль показывает свое название":
 * - the loaded queue profile (Tabs SSOT, what the tab button shows) wins;
 * - the legacy param-era key map is the fallback while profiles are not
 *   loaded yet (hotkeys switch to 'cardio'/'derma'/'appointments' keys);
 * - an unknown profile key falls back to the raw key (truthful), never to
 *   the generic all-departments label that masked arbitrary profiles before;
 * - a null tab keeps the existing all-departments label.
 */
import { describe, expect, it } from 'vitest';

import { resolveRegistrarTabLabel } from '../registrarHelpers';

const translate = (key: string) => `ru:${key}`;

describe('resolveRegistrarTabLabel (RQ-20)', () => {
  it('returns the all-departments label for a null tab', () => {
    expect(resolveRegistrarTabLabel(null, [], translate)).toBe('ru:tabs_appointments');
  });

  it('prefers the loaded profile label (SSOT shown on the tab button)', () => {
    const profiles = [{
      key: 'synthetic-diagnostics',
      label: 'Синтетическая диагностика',
      title: 'Synthetic Diagnostics',
    }];
    expect(resolveRegistrarTabLabel('synthetic-diagnostics', profiles, translate))
      .toBe('Синтетическая диагностика');
  });

  it('falls back to the profile title when no localized label is present', () => {
    const profiles = [{ key: 'synthetic-diagnostics', title: 'Синтетическая диагностика' }];
    expect(resolveRegistrarTabLabel('synthetic-diagnostics', profiles, translate))
      .toBe('Синтетическая диагностика');
  });

  it('uses the localized legacy key for param-era tab keys before profiles load', () => {
    expect(resolveRegistrarTabLabel('cardio', [], translate)).toBe('ru:tabs_cardio');
    expect(resolveRegistrarTabLabel('derma', [], translate)).toBe('ru:tabs_derma');
    expect(resolveRegistrarTabLabel('appointments', [], translate)).toBe('ru:tabs_appointments');
  });

  it('prefers the profile label over the legacy map when both exist', () => {
    const profiles = [{ key: 'lab', label: 'Лаборатория (профиль)' }];
    expect(resolveRegistrarTabLabel('lab', profiles, translate)).toBe('Лаборатория (профиль)');
  });

  it('returns the raw key for an unknown profile with nothing loaded', () => {
    expect(resolveRegistrarTabLabel('synthetic-diagnostics', [], translate))
      .toBe('synthetic-diagnostics');
  });

  it('ignores blank profile labels and falls through to the raw key', () => {
    const profiles = [{ key: 'synthetic-diagnostics', label: '   ' }];
    expect(resolveRegistrarTabLabel('synthetic-diagnostics', profiles, translate))
      .toBe('synthetic-diagnostics');
  });
});
