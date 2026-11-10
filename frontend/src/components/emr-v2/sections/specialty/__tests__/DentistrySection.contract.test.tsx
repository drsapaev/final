
/**
 * DENTPOCKET-FE-001 / DENTDATA-FE-001 / DENTCHART-FE-001 / DENTCHART-FE-002 /
 * DENTCHART-FE-003 (audit 3886 round 26).
 *
 * Red-first contract suite for the EMR dentistry section. On pre-fix source:
 *  - DENTPOCKET-FE-001: the per-tooth periodontal depth inputs parsed the
 *    React change EVENT object with `parseFloat(e as unknown as string) || 0`,
 *    so every entered depth (4 / 6 / 7.5 mm — including severe 6+ mm pockets)
 *    was stored as a fabricated 0 mm "normal" measurement;
 *  - DENTDATA-FE-001: the hygiene/occlusion/radiograph EMRTextFields were
 *    wired to the legacy `onChange` and stored the event-like object
 *    ({ target: { value } }) into specialty_data instead of the typed value;
 *  - DENTCHART-FE-001: the tooth chart kept the previous patient/visit local
 *    state (tooth selection) when the parent switched the patient — a
 *    cross-patient contamination vector;
 *  - DENTCHART-FE-002: with readOnly=true the chart still invoked the EMR
 *    mutation callback on tooth activation;
 *  - DENTCHART-FE-003: Clear All cleared only the local chart while the
 *    canonical specialty_data.tooth_status kept every "removed" status.
 */
import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DentistrySection } from '../DentistrySection';
import { TOOTH_STATUS } from '@/components/dental/dentalConstants';

vi.mock('@/i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      (params ? `${key}:${JSON.stringify(params)}` : key),
  }),
}));
vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({}),
}));
vi.mock('../../EMRSection', () => ({
  default: ({ children }: { children: React.ReactNode }) =>
    React.createElement('section', null, children),
}));

const toothButton = (toothNumber: number) =>
  screen.getByRole('button', { name: new RegExp(`"toothNumber":${toothNumber}`) });

type ChangeCall = [field: string, value: unknown];

/**
 * Mounts DentistrySection with a stateful specialty_data owner so emitted
 * changes flow back through props exactly like EMRContainerV2 does.
 */
function renderStateful(initialSpecialty: Record<string, unknown> = {}) {
  const calls: ChangeCall[] = [];
  const Harness = () => {
    const [specialty, setSpecialty] = useState(initialSpecialty);
    return (
      <DentistrySection
        toothStatus={(specialty.tooth_status as Record<string, unknown>) || {}}
        hygieneIndices={(specialty.hygiene_indices as Record<string, unknown>) || {}}
        periodontalPockets={(specialty.periodontal_pockets as Record<string, unknown>) || {}}
        measurements={(specialty.measurements as Record<string, unknown>) || {}}
        radiographs={(specialty.radiographs as Record<string, unknown>) || {}}
        onChange={(field, value) => {
          calls.push([field, value]);
          setSpecialty((prev) => ({ ...prev, [field]: value }));
        }}
      />
    );
  };
  render(<Harness />);
  return calls;
}

describe('DentistrySection clinical data contracts (audit 3886 round 26)', () => {
  it('stores the typed periodontal depth exactly and keeps unmeasured teeth unmeasured (DENTPOCKET-FE-001)', () => {
    const calls = renderStateful();
    fireEvent.click(screen.getByRole('button', { name: 'Пародонт' }));

    const tooth16 = screen.getByLabelText('Periodontal pocket depth for tooth 16');
    const tooth46 = screen.getByLabelText('Periodontal pocket depth for tooth 46');

    // 4 mm — a moderate pocket, stored exactly as typed (not 0)
    fireEvent.change(tooth16, { target: { value: '4' } });
    expect(calls.at(-1)).toEqual(['periodontal_pockets', { 16: 4 }]);
    expect(tooth16).toHaveProperty('value', '4');

    // 7.5 mm — a severe pocket, stored exactly as typed (not 0)
    fireEvent.change(tooth46, { target: { value: '7.5' } });
    expect(calls.at(-1)).toEqual(['periodontal_pockets', { 16: 4, 46: 7.5 }]);
    expect(tooth46).toHaveProperty('value', '7.5');

    // Severe/moderate classification follows the STORED measurements
    expect(document.querySelectorAll('.periodontal-tooth.severe')).toHaveLength(1);
    expect(document.querySelectorAll('.periodontal-tooth.moderate')).toHaveLength(1);

    // Stats: avg (4+7.5)/2 = 5.8 mm, max 7.5 mm
    expect(screen.getByText('5.8')).toBeTruthy();
    expect(screen.getByText('7.5')).toBeTruthy();

    // Clearing a measured tooth keeps it explicitly unmeasured — the doctor
    // sees an empty input, never a fabricated 0 mm "normal" pocket
    fireEvent.change(tooth16, { target: { value: '' } });
    expect(calls.at(-1)).toEqual(['periodontal_pockets', { 46: 7.5 }]);
    expect(tooth16).toHaveProperty('value', '');
    expect(document.querySelectorAll('.periodontal-tooth.moderate')).toHaveLength(0);

    // Out-of-range input (declared 0–15 mm) is refused: nothing is stored
    // and the next committed change snaps the field back to 7.5
    fireEvent.change(tooth46, { target: { value: '20' } });
    expect(calls.at(-1)).toEqual(['periodontal_pockets', { 46: 7.5 }]);
    fireEvent.change(tooth16, { target: { value: '6' } });
    expect(calls.at(-1)).toEqual(['periodontal_pockets', { 46: 7.5, 16: 6 }]);
    expect(tooth46).toHaveProperty('value', '7.5');
  });

  it('stores scalar values, not event objects, for hygiene/occlusion/radiograph fields (DENTDATA-FE-001)', () => {
    const calls = renderStateful();
    fireEvent.click(screen.getByRole('button', { name: 'Гигиена' }));

    fireEvent.change(screen.getByLabelText('OHIS (Oral Hygiene Index Simplified)'), {
      target: { value: '2.5' },
    });
    expect(calls.at(-1)).toEqual(['hygiene_indices', { ohis: '2.5' }]);

    fireEvent.change(screen.getByLabelText('Bleeding Index (%)'), {
      target: { value: '10' },
    });
    expect(calls.at(-1)).toEqual(['hygiene_indices', { ohis: '2.5', bleeding: '10' }]);

    fireEvent.click(screen.getByRole('button', { name: 'Прикус' }));
    fireEvent.change(screen.getByLabelText('misc.ds_overjet_mm'), { target: { value: '3.5' } });
    expect(calls.at(-1)).toEqual(['measurements', { overjet: '3.5' }]);

    fireEvent.click(screen.getByRole('button', { name: 'Рентген' }));
    fireEvent.change(screen.getByLabelText('misc.ds_panoramnyy_snimok'), {
      target: { value: 'synthetic://pano.dcm' },
    });
    expect(calls.at(-1)).toEqual(['radiographs', { panoramic: 'synthetic://pano.dcm' }]);
  });

  it('recovers a scalar display from legacy event-object records (DENTDATA-FE-001 read boundary)', () => {
    render(
      <DentistrySection
        hygieneIndices={{ ohis: { target: { value: '2.5' } } } as Record<string, unknown>}
        measurements={{ overjet: { target: { value: '3.5' } } } as Record<string, unknown>}
        onChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Гигиена' }));
    expect(screen.getByLabelText('OHIS (Oral Hygiene Index Simplified)')).toHaveProperty(
      'value',
      '2.5',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Прикус' }));
    expect(screen.getByLabelText('misc.ds_overjet_mm')).toHaveProperty('value', '3.5');
  });

  it('never dispatches specialty_data changes from a read-only chart (DENTCHART-FE-002)', () => {
    const onChange = vi.fn();
    render(
      <DentistrySection
        toothStatus={{ 16: { status: TOOTH_STATUS.CARIES } }}
        onChange={onChange}
        disabled
      />,
    );

    // Keyboard activation of the focused tooth button synthesizes a click;
    // a locked chart must never reach the parent EMR mutation callback.
    toothButton(16).focus();
    fireEvent.click(toothButton(16));

    expect(onChange).not.toHaveBeenCalled();
    expect(toothButton(16).getAttribute('aria-label')).toContain('Кариес');
  });

  it('Clear All clears the canonical tooth_status, not only the local chart (DENTCHART-FE-003)', () => {
    const calls = renderStateful({
      tooth_status: {
        16: { status: TOOTH_STATUS.CARIES },
        46: { status: TOOTH_STATUS.CROWN },
      },
    });

    expect(screen.getByText('Кариес: 1')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tc_btn_clear' }));

    // The owner received an explicit controlled clear
    expect(calls.at(-1)).toEqual(['tooth_status', {}]);
    // ...and the chart re-rendered from the now-empty canonical state
    expect(toothButton(16).getAttribute('aria-label')).toContain('Здоров');
    expect(screen.queryByText('Кариес: 1')).toBeNull();

    // A fresh entry after the clear can never resurrect "cleared" statuses
    fireEvent.click(toothButton(16));
    expect(calls.at(-1)).toEqual(['tooth_status', { 16: {} }]);
  });

  it('drops patient A chart state when the same-mounted section switches to patient B (DENTCHART-FE-001)', () => {
    const onChange = vi.fn();
    const view = render(
      <DentistrySection
        patientId={7}
        visitId={41}
        toothStatus={{ 16: { status: TOOTH_STATUS.CARIES } }}
        onChange={onChange}
      />,
    );

    // Patient A: select tooth 16 in the editable chart
    fireEvent.click(toothButton(16));
    expect(toothButton(16).style.border).toContain('--mac-accent-blue');

    // Same-mounted switch to patient B with a clean chart
    view.rerender(
      <DentistrySection
        patientId={8}
        visitId={42}
        toothStatus={{}}
        onChange={onChange}
      />,
    );

    // B shows only B's state: no A caries label and no A selection remnant
    expect(toothButton(16).getAttribute('aria-label')).toContain('Здоров');
    expect(toothButton(16).style.border).not.toContain('--mac-accent-blue');

    // Clicking in B's chart can never write patient A's values
    fireEvent.click(toothButton(16));
    expect(onChange).toHaveBeenLastCalledWith('tooth_status', { 16: {} });
  });
});
