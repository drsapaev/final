/**
 * Audit 3892 round 1 — fail-first regressions for TreatmentPlanner
 * hydration and patient-context isolation.
 *
 * Covers:
 *  - DENTPLAN-FE-001: reopening a saved dental treatment plan must hydrate
 *    the existing stages from the EMR instead of starting blank, and Save
 *    must preserve them (no silent plan replacement).
 *  - DENTPLAN-FE-002: an open planner must drop patient A's unsaved stages
 *    when the parent switches the visit, and an in-flight save must abort
 *    when the visit changes before the POST.
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '../../../api/client';
import TreatmentPlanner from '../TreatmentPlanner';

vi.mock('../../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../../services/notify', () => ({
  default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../utils/printWindow', () => ({
  openPrintableWindow: vi.fn(),
}));
vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({}),
}));
vi.mock('../../../i18n/useTranslation', () => {
  return {
    useTranslation: () => ({ t: (key: string) => key }),
    TranslationProvider: ({ children }: { children: unknown }) => children,
  };
});

const stage = (name: string) => ({
  id: `stage_${name}`,
  name,
  description: `SYNTHETIC ${name} description`,
  teeth: [16],
  date: '2026-11-01',
  duration: 1,
  cost: 1000,
  priority: 'medium',
  status: 'planned',
});

const emrWithPlan = (stages: unknown[], rowVersion = 4) => ({
  status: 200,
  data: {
    data: {
      specialty: 'dentistry',
      specialty_data: {
        treatment_plan: { name: 'SYNTHETIC existing plan', stages, totalCost: stages.length * 1000, totalDuration: stages.length },
      },
    },
    row_version: rowVersion,
    patient_id: 7,
    visit_id: 41,
  },
});

const emrWithoutPlan = (rowVersion = 6) => ({
  status: 200,
  data: { data: { specialty: 'dentistry', specialty_data: {} }, row_version: rowVersion, patient_id: 8, visit_id: 42 },
});

const addStageThroughDialog = (name: string) => {
  fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tp_add_stage' }));
  // The macos Input does not bind its label to an accessible name; the stage
  // name field is the first textbox inside the stage dialog.
  const dialog = screen.getByRole('dialog');
  const stageNameInput = within(dialog).getAllByRole('textbox')[0];
  fireEvent.change(stageNameInput, { target: { value: name } });
  fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tp_add' }));
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('TreatmentPlanner hydration and identity (audit 3892 round 1)', () => {
  it('DENTPLAN-FE-001: hydrates the saved plan and preserves its stages on save', async () => {
    vi.mocked(api.get).mockResolvedValue(emrWithPlan([stage('Alpha'), stage('Beta'), stage('Gamma')]) as never);
    vi.mocked(api.post).mockResolvedValue({ data: { row_version: 5 } } as never);
    render(<TreatmentPlanner visitId={41} patientId={7} />);

    // The three pre-existing stages are visible immediately (not a blank plan).
    expect(await screen.findByText('Alpha')).toBeTruthy();
    expect(screen.getByText('Beta')).toBeTruthy();
    expect(screen.getByText('Gamma')).toBeTruthy();

    addStageThroughDialog('Delta');
    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tp_save_plan' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [url, payload] = vi.mocked(api.post).mock.calls[0];
    expect(url).toBe('/v2/emr/41');
    const plan = (payload as { data: { specialty_data: { treatment_plan: { stages: unknown[] } } } })
      .data.specialty_data.treatment_plan;
    expect((plan.stages as Array<{ name: string }>).map((s) => s.name)).toEqual(['Alpha', 'Beta', 'Gamma', 'Delta']);
    expect((payload as { row_version?: number }).row_version).toBe(4);
  });

  it('DENTPLAN-FE-002: drops patient A\'s unsaved stages when the visit switches to B', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => Promise.resolve(
      String(url).endsWith('/41') ? emrWithPlan([stage('Alpha')]) : emrWithoutPlan(),
    ) as never);
    vi.mocked(api.post).mockResolvedValue({ data: { row_version: 7 } } as never);

    const view = render(<TreatmentPlanner visitId={41} patientId={7} />);
    expect(await screen.findByText('Alpha')).toBeTruthy();

    addStageThroughDialog('Unsaved-A-stage');

    view.rerender(<TreatmentPlanner visitId={42} patientId={8} />);

    await waitFor(() => expect(screen.queryByText('Alpha')).toBeNull());
    await waitFor(() => expect(screen.queryByText('Unsaved-A-stage')).toBeNull());
    // Editing for B reopens only after B's hydration read succeeds (review
    // 3903 P1: no unhydrated editable plan).
    await screen.findByText('dental.dental_tp_empty_plan');

    addStageThroughDialog('B-stage');
    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tp_save_plan' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [url, payload] = vi.mocked(api.post).mock.calls[0];
    expect(url).toBe('/v2/emr/42');
    const plan = (payload as { data: { specialty_data: { treatment_plan: { stages: unknown[] } } } })
      .data.specialty_data.treatment_plan;
    expect((plan.stages as Array<{ name: string }>).map((s) => s.name)).toEqual(['B-stage']);
  });

  it('DENTPLAN-FE-002: aborts an in-flight save when the visit changes before the POST', async () => {
    // GET #1 hydrates visit 41 (ready); GET #2 is the save-time read that
    // hangs while the visit switches; GET #3 re-hydrates visit 42.
    let getCalls = 0;
    let resolveSaveGet: ((value: unknown) => void) | undefined;
    vi.mocked(api.get).mockImplementation(() => {
      getCalls += 1;
      if (getCalls === 2) {
        return new Promise((resolve) => { resolveSaveGet = resolve; }) as never;
      }
      return Promise.resolve(emrWithoutPlan()) as never;
    });

    const view = render(<TreatmentPlanner visitId={41} patientId={7} />);
    await screen.findByText('dental.dental_tp_empty_plan');
    addStageThroughDialog('In-flight-A');

    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tp_save_plan' }));
    expect(api.get).toHaveBeenCalled();

    // The visit changes while the save-time GET is still pending.
    view.rerender(<TreatmentPlanner visitId={42} patientId={8} />);

    await act(async () => {
      resolveSaveGet?.(emrWithPlan([stage('In-flight-A')]));
      await Promise.resolve();
    });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });

    // The stale A-context save must not land as a POST at all.
    expect(api.post).not.toHaveBeenCalled();
  });

  it('review 3903 P1 (DENTPLAN): a failed hydration GET fails closed — no editable empty plan, no save', async () => {
    let hydrationAttempts = 0;
    vi.mocked(api.get).mockImplementation(() => {
      hydrationAttempts += 1;
      return hydrationAttempts === 1
        ? Promise.reject(new Error('network unavailable')) as never
        : Promise.resolve(emrWithPlan([stage('Alpha'), stage('Beta')])) as never;
    });
    vi.mocked(api.post).mockResolvedValue({ data: { row_version: 5 } } as never);
    render(<TreatmentPlanner visitId={41} patientId={7} />);

    // Fail closed: the error is surfaced, editing and saving stay disabled,
    // and the empty-plan hint is not offered as editable bait.
    expect(await screen.findByText('dental2.treatment_plan_load_failed')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'dental.dental_tp_add_stage' })).toHaveProperty('disabled', true);
    expect(screen.queryByText('dental.dental_tp_empty_plan')).toBeNull();
    expect(screen.queryByRole('button', { name: 'dental.dental_tp_save_plan' })).toBeNull();
    expect(api.post).not.toHaveBeenCalled();

    // The retry reloads the saved stages and reopens the editor.
    fireEvent.click(screen.getByRole('button', { name: 'doctor.btn_retry' }));
    expect(await screen.findByText('Alpha')).toBeTruthy();
    expect(screen.getByText('Beta')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'dental.dental_tp_add_stage' })).toHaveProperty('disabled', false);
  });

  it('review 3903 P1 (DENTPLAN): editing stays disabled until a slow hydration GET lands', async () => {
    let resolveHydration: ((value: unknown) => void) | undefined;
    vi.mocked(api.get).mockImplementation(() => new Promise((resolve) => {
      resolveHydration = resolve;
    }) as never);
    render(<TreatmentPlanner visitId={41} patientId={7} />);

    // While the hydration read is pending the plan is not editable and not
    // savable — stages entered meanwhile cannot exist, so a late response
    // cannot clobber anything and an unhydrated plan cannot be saved.
    expect(screen.getByRole('button', { name: 'dental.dental_tp_add_stage' })).toHaveProperty('disabled', true);
    expect(screen.queryByRole('button', { name: 'dental.dental_tp_save_plan' })).toBeNull();

    await act(async () => {
      resolveHydration?.(emrWithPlan([stage('Alpha')]));
      await Promise.resolve();
    });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });

    expect(await screen.findByText('Alpha')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'dental.dental_tp_add_stage' })).toHaveProperty('disabled', false);
  });
});
