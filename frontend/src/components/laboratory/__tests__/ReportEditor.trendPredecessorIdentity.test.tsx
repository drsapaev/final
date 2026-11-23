/**
 * LABEDIT-FE-003 / LABEDIT-FE-004 (post-merge review of #3916, ledger group
 * «report value editor, previous-result trend») — fail-first regressions:
 *
 * **LABEDIT-FE-003 (P1):** after report A's `getInstance(prevA)` resolves,
 * `previousInstanceDetails` holds A's analytes. Switching to report B
 * (potentially another patient) starts B's asynchronous GET but does NOT
 * drop A's details — until B's request resolves (or fails / sticks), the
 * editor renders A's clinical `value_text` beside B's fields, labeled with
 * B's predecessor `created_at`. The old request-cancellation guard cannot
 * help because A's response had already completed. The details must be
 * bound to the predecessor + patient identity they were fetched for and
 * dropped synchronously on identity change; same-patient scope enforced.
 *
 * **LABEDIT-FE-004 (P2):** `find(first non-current same-template)` can show
 * a FUTURE result as the «previous» value — the history list is
 * newest-first, so an operator opening an OLDER report (active #90 from
 * October, history contains newer #91 from November and older #89 from
 * September) gets #91 as the trend predecessor. The predecessor must be
 * the chronologically OLDER same-template entry (deterministic id/date
 * tie-break), the nearest preceding one, without relying on list order.
 *
 * Red-first: on the pre-fix source (1) A's «135» survives the A→B switch,
 * (2) an entry of another patient is selected, (3) a details DTO claiming
 * another patient still renders, (4) the FUTURE entry #91 is fetched as
 * the predecessor of the older active report #90, and (5) the id tie-break
 * picks the newer #91 for an equal created_at.
 */
import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

const getInstanceMock = vi.hoisted(() => vi.fn());

vi.mock('../../api/labReporting', () => ({
  labReportingApi: {
    getInstance: getInstanceMock,
    listInstances: vi.fn(),
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    finalize: vi.fn(),
    revise: vi.fn(),
    downloadPdf: vi.fn(),
    markPrinted: vi.fn(),
    previewInstancePdf: vi.fn(),
  },
}));

vi.mock('../../../hooks/useLabReporting', () => {
  // Production `useLabReporting` returns a STABLE module-level singleton;
  // the mock mirrors that contract (a per-render object would exercise an
  // artificial dependency identity churn the real hook never exhibits).
  const mockedApi = {
    getInstance: getInstanceMock,
    listInstances: vi.fn(),
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    finalize: vi.fn(),
    revise: vi.fn(),
    downloadPdf: vi.fn(),
    markPrinted: vi.fn(),
    previewInstancePdf: vi.fn(),
  };
  return { useLabReporting: () => mockedApi };
});

vi.mock('./hooks/useLabToast', () => ({
  useLabToast: () => ({
    interactiveInfo: vi.fn(),
    interactiveWarning: vi.fn(),
    interactiveError: vi.fn(),
  }),
}));

import ReportEditorRaw from '../ReportEditor';

const ReportEditor = ReportEditorRaw as unknown as React.ComponentType<Record<string, unknown>>;

const hgbField = (value: string) => ({
  field_key: 'hgb',
  label: 'Гемоглобин',
  value_type: 'numeric',
  value_text: value,
  unit: 'г/л',
  reference_text: '130-170',
  resolved_flag: null,
  resolved_flag_severity: null,
  required: true,
});

// Patient 1's newest report (the «A» of the P1 switch scenario).
const REPORT_A = {
  id: 91,
  patient_id: 1,
  template_id: 3,
  status: 'IN_PROGRESS',
  created_at: '2026-11-07T10:00:00Z',
  sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('5.0')] }],
};

const HISTORY_A = [
  { id: 91, patient_id: 1, template_id: 3, created_at: '2026-11-07T10:00:00Z' },
  { id: 90, patient_id: 1, template_id: 3, created_at: '2026-10-05T10:00:00Z' },
  { id: 80, patient_id: 1, template_id: 7, created_at: '2026-09-01T10:00:00Z' },
];

const PREV_DETAILS_A = {
  id: 90,
  patient_id: 1,
  template_id: 3,
  status: 'FINALIZED',
  created_at: '2026-10-05T10:00:00Z',
  sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('135')] }],
};

// Patient 2's newest report (the «B» of the P1 switch scenario).
const REPORT_B = {
  id: 95,
  patient_id: 2,
  template_id: 3,
  status: 'IN_PROGRESS',
  created_at: '2026-11-08T10:00:00Z',
  sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('10.0')] }],
};

const HISTORY_B = [
  { id: 95, patient_id: 2, template_id: 3, created_at: '2026-11-08T10:00:00Z' },
  { id: 94, patient_id: 2, template_id: 3, created_at: '2026-11-06T10:00:00Z' },
];

const PREV_DETAILS_B = {
  id: 94,
  patient_id: 2,
  template_id: 3,
  status: 'FINALIZED',
  created_at: '2026-11-06T10:00:00Z',
  sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('140')] }],
};

const baseProps = {
  activeInstance: REPORT_A,
  draftValues: {} as Record<string, string>,
  collapsedSections: new Set(),
  onToggleSection: vi.fn(),
  onUpdateField: vi.fn(),
  canEditActiveInstance: true,
  reportHistory: HISTORY_A,
  notify: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
  getInstanceMock.mockReset();
  getInstanceMock.mockResolvedValue(null);
});

const flush = () => new Promise((resolve) => { setTimeout(resolve, 60); });

describe('LABEDIT-FE-003 — the previous report’s trend details are dropped synchronously on predecessor/patient change', () => {
  it('A→B report switch: A’s trend disappears while B’s detail GET is pending, then B’s own predecessor value renders (pre-fix: A’s «135» survives the switch)', async () => {
    let resolveBDetails!: (value: unknown) => void;
    const deferredB = new Promise<unknown>((resolve) => { resolveBDetails = resolve; });
    getInstanceMock.mockImplementation((id: number) =>
      (id === 90 ? Promise.resolve(PREV_DETAILS_A) : deferredB));

    const { rerender } = render(
      <ThemeProvider>
        <ReportEditor {...baseProps} />
      </ThemeProvider>
    );

    // Report A (patient 1): its predecessor's (id 90) trend value renders.
    await waitFor(() => expect(getInstanceMock).toHaveBeenCalledWith(90));
    await waitFor(() => expect(screen.getByText(/135/)).toBeInTheDocument());
    expect(screen.getByText(/окт\./)).toBeInTheDocument();

    // Switch to report B (patient 2) whose predecessor GET sticks pending.
    rerender(
      <ThemeProvider>
        <ReportEditor
          {...baseProps}
          activeInstance={REPORT_B}
          reportHistory={HISTORY_B}
        />
      </ThemeProvider>
    );

    // While B's GET is pending, NOTHING renders as B's previous value —
    // in particular A's «135» (another patient's clinical value) is gone.
    await act(async () => { await flush(); });
    expect(screen.queryByText(/135/)).toBeNull();
    expect(screen.queryByText(/↗/)).toBeNull();

    // B's own predecessor (id 94) is fetched and its value renders.
    await act(async () => { resolveBDetails(PREV_DETAILS_B); });
    await waitFor(() => expect(getInstanceMock).toHaveBeenCalledWith(94));
    await waitFor(() => expect(screen.getByText(/140/)).toBeInTheDocument());
    expect(screen.getByText(/нояб\./)).toBeInTheDocument();
    // A's predecessor is never re-fetched for B.
    expect(getInstanceMock).not.toHaveBeenCalledWith(91);
  });

  it('an older history entry of ANOTHER patient is never selected as the predecessor (same-patient scope)', async () => {
    // Active B (patient 2); history contains an older same-template entry
    // of patient 1 (id 94) and an older same-template entry of patient 2
    // (id 93). Only 93 qualifies.
    getInstanceMock.mockResolvedValue({
      id: 93,
      patient_id: 2,
      template_id: 3,
      created_at: '2026-11-05T10:00:00Z',
      sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('130')] }],
    });

    render(
      <ThemeProvider>
        <ReportEditor
          {...baseProps}
          activeInstance={REPORT_B}
          reportHistory={[
            { id: 95, patient_id: 2, template_id: 3, created_at: '2026-11-08T10:00:00Z' },
            { id: 94, patient_id: 1, template_id: 3, created_at: '2026-11-07T10:00:00Z' },
            { id: 93, patient_id: 2, template_id: 3, created_at: '2026-11-05T10:00:00Z' },
          ]}
        />
      </ThemeProvider>
    );

    await waitFor(() => expect(getInstanceMock).toHaveBeenCalledWith(93));
    expect(getInstanceMock).not.toHaveBeenCalledWith(94);
    await waitFor(() => expect(screen.getByText(/↗ 130/)).toBeInTheDocument());
  });

  it('a details DTO claiming another patient is suppressed entirely (fail-closed)', async () => {
    // Entry 94 (patient 2) is selected, but the resolved DETAILS carry
    // patient_id 1 — a backend inconsistency must never surface another
    // patient's value as this report's trend.
    getInstanceMock.mockResolvedValue({
      id: 94,
      patient_id: 1,
      template_id: 3,
      created_at: '2026-11-06T10:00:00Z',
      sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('140')] }],
    });

    render(
      <ThemeProvider>
        <ReportEditor
          {...baseProps}
          activeInstance={REPORT_B}
          reportHistory={HISTORY_B}
        />
      </ThemeProvider>
    );

    await act(async () => { await flush(); });
    await waitFor(() => expect(getInstanceMock).toHaveBeenCalledWith(94));
    expect(screen.queryByText(/140/)).toBeNull();
    expect(screen.queryByText(/↗/)).toBeNull();
  });
});

describe('LABEDIT-FE-004 — the previous value is a chronologically OLDER same-template result', () => {
  it('an older active report never takes a FUTURE same-template entry as its previous value (pre-fix: November’s #91 shown for October’s #90)', async () => {
    // The operator opens the OLDER report #90 (October). History contains
    // the newer #91 (November) and the older #89 (September).
    getInstanceMock.mockResolvedValue({
      id: 89,
      patient_id: 1,
      template_id: 3,
      created_at: '2026-09-01T10:00:00Z',
      sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('120')] }],
    });

    render(
      <ThemeProvider>
        <ReportEditor
          {...baseProps}
          activeInstance={{
            id: 90,
            patient_id: 1,
            template_id: 3,
            status: 'FINALIZED',
            created_at: '2026-10-05T10:00:00Z',
            sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('128')] }],
          }}
          reportHistory={[
            { id: 91, patient_id: 1, template_id: 3, created_at: '2026-11-07T10:00:00Z' },
            { id: 90, patient_id: 1, template_id: 3, created_at: '2026-10-05T10:00:00Z' },
            { id: 89, patient_id: 1, template_id: 3, created_at: '2026-09-01T10:00:00Z' },
          ]}
        />
      </ThemeProvider>
    );

    // The predecessor is the chronologically OLDER #89 — never the future #91.
    await waitFor(() => expect(getInstanceMock).toHaveBeenCalledWith(89));
    expect(getInstanceMock).not.toHaveBeenCalledWith(91);
    await waitFor(() => expect(screen.getByText(/120/)).toBeInTheDocument());
    expect(screen.getByText(/сент\./)).toBeInTheDocument();
  });

  it('deterministic id tie-break for an equal created_at: the smaller id precedes, the greater id is future (pre-fix: #91 picked)', async () => {
    getInstanceMock.mockResolvedValue({
      id: 89,
      patient_id: 1,
      template_id: 3,
      created_at: '2026-10-05T10:00:00Z',
      sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('110')] }],
    });

    render(
      <ThemeProvider>
        <ReportEditor
          {...baseProps}
          activeInstance={{
            id: 90,
            patient_id: 1,
            template_id: 3,
            status: 'FINALIZED',
            created_at: '2026-10-05T10:00:00Z',
            sections: [{ key: 'cbc', title: 'CBC', fields: [hgbField('128')] }],
          }}
          reportHistory={[
            { id: 91, patient_id: 1, template_id: 3, created_at: '2026-10-05T10:00:00Z' },
            { id: 89, patient_id: 1, template_id: 3, created_at: '2026-10-05T10:00:00Z' },
            { id: 90, patient_id: 1, template_id: 3, created_at: '2026-10-05T10:00:00Z' },
          ]}
        />
      </ThemeProvider>
    );

    await waitFor(() => expect(getInstanceMock).toHaveBeenCalledWith(89));
    expect(getInstanceMock).not.toHaveBeenCalledWith(91);
    await waitFor(() => expect(screen.getByText(/110/)).toBeInTheDocument());
  });

  it('control: the newest active report still renders its immediate predecessor trend', async () => {
    getInstanceMock.mockResolvedValue(PREV_DETAILS_A);

    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} />
      </ThemeProvider>
    );

    await waitFor(() => expect(getInstanceMock).toHaveBeenCalledWith(90));
    await waitFor(() => expect(screen.getByText(/135/)).toBeInTheDocument());
    expect(screen.getByText(/окт\./)).toBeInTheDocument();
  });
});
