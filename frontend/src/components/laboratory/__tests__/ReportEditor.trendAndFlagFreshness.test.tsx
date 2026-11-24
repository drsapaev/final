/**
 * LABEDIT-FE-001 / LABEDIT-FE-002 (audit 3886, ledger group «report value
 * editor, previous-result trend and flag freshness») — fail-first
 * regressions:
 *
 * **LABEDIT-FE-001 (P2):** the per-field previous-result trend read
 * `reportHistory[1].sections`, but the list API returns summary DTOs
 * WITHOUT `sections` (backend `LabReportInstanceSummaryOut`) — the trend
 * was unreachable for any real response, and `[1]` was not even the
 * preceding same-template instance. The trend must come from the
 * authorized DETAILS of the actual preceding same-template instance.
 *
 * **LABEDIT-FE-002 (P1):** the persisted clinical flag badge is rendered
 * beside the UNSAVED draft value — a lab operator changes 5.0→200 while
 * the badge still says «норма» (or 200→5.0 while it says «критично»).
 * While the draft differs from the persisted value, the badge must not
 * present the stored flag as if it described the draft input.
 *
 * Red-first: on the pre-fix source (1) the trend never renders for
 * summary-shaped history entries, and (2) the «норма» badge renders beside
 * a differing draft value.
 */
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

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

vi.mock('../../../hooks/useLabReporting', () => ({
  useLabReporting: () => ({
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
  }),
}));

import ReportEditorRaw from '../ReportEditor';
import { readReportDraft } from '../hooks/useLabReportState';

const ReportEditor = ReportEditorRaw as unknown as React.ComponentType<Record<string, unknown>>;

// Fixtures carry the real DTO contract: LabReportInstanceOut /
// LabReportInstanceSummaryOut always include patient_id and created_at
// (the LABEDIT-FE-003 same-patient scope relies on them).
const ACTIVE_INSTANCE = {
  id: 91,
  patient_id: 1,
  template_id: 3,
  status: 'IN_PROGRESS',
  created_at: '2026-11-07T10:00:00Z',
  sections: [
    {
      key: 'cbc',
      title: 'CBC',
      fields: [
        {
          field_key: 'hgb',
          label: 'Гемоглобин',
          value_type: 'numeric',
          value_text: '5.0',
          unit: 'г/л',
          reference_text: '130-170',
          resolved_flag: null,
          resolved_flag_severity: null,
          evaluation_status: 'evaluated',
          interpretation: 'normal',
          required: true,
        },
      ],
    },
  ],
};

// Real list-API contract: summary DTOs WITHOUT `sections`.
const HISTORY = [
  { id: 91, patient_id: 1, template_id: 3, created_at: '2026-11-07T10:00:00Z' },
  { id: 90, patient_id: 1, template_id: 3, created_at: '2026-10-05T10:00:00Z' },
  { id: 80, patient_id: 1, template_id: 7, created_at: '2026-09-01T10:00:00Z' },
];

const PREV_DETAILS = {
  id: 90,
  patient_id: 1,
  template_id: 3,
  status: 'FINALIZED',
  created_at: '2026-10-05T10:00:00Z',
  sections: [
    {
      key: 'cbc',
      title: 'CBC',
      fields: [
        { field_key: 'hgb', label: 'Гемоглобин', value_type: 'numeric', value_text: '135', unit: 'г/л', reference_text: '130-170', resolved_flag: 'low', resolved_flag_severity: 1 },
      ],
    },
  ],
};

const baseProps = {
  activeInstance: ACTIVE_INSTANCE,
  draftValues: {} as Record<string, string>,
  collapsedSections: new Set(),
  onToggleSection: vi.fn(),
  onUpdateField: vi.fn(),
  canEditActiveInstance: true,
  reportHistory: HISTORY,
  notify: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
  getInstanceMock.mockReset();
  // Default: no previous-instance details (FE-002 tests do not need the
  // trend; a resolved null keeps the effect's promise chain well-formed).
  getInstanceMock.mockResolvedValue(null);
});

describe('LABEDIT-FE-001 — the previous-value trend reads the preceding same-template instance details', () => {
  it('renders the previous same-template field value from the fetched details (pre-fix: summary DTOs have no sections — trend unreachable)', async () => {
    getInstanceMock.mockResolvedValue(PREV_DETAILS);

    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} />
      </ThemeProvider>
    );

    // The preceding same-template instance (id 90) details are fetched.
    await waitFor(() => expect(getInstanceMock).toHaveBeenCalledWith(90));

    // The trend surfaces the previous hgb value (135) with its date —
    // sourced from the details DTO, not from a summary row.
    await waitFor(() => {
      expect(screen.getByText(/135/)).toBeInTheDocument();
    });
    expect(screen.getByText(/окт\./)).toBeInTheDocument();
  });

  it('a different-template predecessor is never fetched or shown', async () => {
    // Only a cross-template predecessor exists (template_id 7).
    render(
      <ThemeProvider>
        <ReportEditor
          {...baseProps}
          reportHistory={[{ id: 91, patient_id: 1, template_id: 3, created_at: '2026-11-07T10:00:00Z' }, { id: 80, patient_id: 1, template_id: 7, created_at: '2026-09-01T10:00:00Z' }]}
        />
      </ThemeProvider>
    );

    await new Promise((resolve) => { setTimeout(resolve, 80); });
    expect(getInstanceMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/Ранее /)).toBeNull();
  });
});

describe('LABEDIT-FE-002 — the persisted flag badge is not presented beside a differing draft value', () => {
  it('a differing draft value suppresses the stored «норма» badge and marks the flag as unsaved (pre-fix: «норма» shown beside 200)', async () => {
    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} draftValues={{ hgb: '200' }} />
      </ThemeProvider>
    );

    // The persisted flag said «норма» for the stored 5.0 — it must NOT be
    // displayed as if it described the unsaved draft 200.
    await waitFor(() => {
      expect(screen.queryByText('норма')).toBeNull();
    });
    // The field is visibly marked as an unsaved draft instead.
    expect(screen.getByText(/черновик/i)).toBeInTheDocument();
  });

  it('control: an unchanged draft keeps the authoritative persisted flag badge', async () => {
    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} draftValues={{ hgb: '5.0' }} />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('норма')).toBeInTheDocument();
    });
    expect(screen.queryByText(/черновик/i)).toBeNull();
  });

  it('does not present an absent evaluation as normal', () => {
    const section = ACTIVE_INSTANCE.sections[0];
    const field = { ...section.fields[0], evaluation_status: 'unknown', interpretation: null };
    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} activeInstance={{ ...ACTIVE_INSTANCE, sections: [{ ...section, fields: [field] }] }} draftValues={{ hgb: '5.0' }} />
      </ThemeProvider>
    );
    expect(screen.getByText('нет сведений об оценке')).toBeInTheDocument();
    expect(screen.queryByText('норма')).toBeNull();
  });

  it('editing the value live swaps the authoritative badge for the unsaved marker', async () => {
    getInstanceMock.mockResolvedValue(PREV_DETAILS);
    // Stateful host: ReportEditor is controlled — onUpdateField must flow
    // back into draftValues for the live-edit assertion.
    function Host() {
      const [draft, setDraft] = React.useState<Record<string, string>>({ hgb: '5.0' });
      return (
        <ThemeProvider>
          <ReportEditor
            {...baseProps}
            draftValues={draft}
            onUpdateField={(key: string, value: string) => setDraft((prev) => ({ ...prev, [key]: value }))}
          />
        </ThemeProvider>
      );
    }
    render(<Host />);

    expect(screen.getByText('норма')).toBeInTheDocument();

    const input = screen.getByDisplayValue('5.0');
    fireEvent.change(input, { target: { value: '210' } });

    await waitFor(() => {
      expect(screen.queryByText('норма')).toBeNull();
    });
    expect(screen.getByText(/черновик/i)).toBeInTheDocument();
  });
});

describe('persisted analyzer warning codes', () => {
  const section = ACTIVE_INSTANCE.sections[0];
  const instrumentFlags = ['SYNTHETIC-B*', 'synthetic-a'];
  const field = { ...section.fields[0], instrument_flags: instrumentFlags };
  const report = {
    ...ACTIVE_INSTANCE,
    sections: [{ ...section, fields: [
      field,
      { ...section.fields[0], field_key: 'other', label: 'SYNTHETIC-NEIGHBOR', required: false },
    ] }],
  };

  afterEach(async () => {
    cleanup();
    await i18n.changeLanguage('ru');
  });

  it.each([
    ['ru', 'Предупреждения анализатора'],
    ['uz-Cyrl', 'Анализатор огоҳлантиришлари'],
    ['uz-Latn', 'Analizator ogohlantirishlari'],
  ])('shows original codes in order for the saved value in %s', async (language, label) => {
    await i18n.changeLanguage(language);
    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} activeInstance={report} draftValues={{ hgb: '5.0', other: '5.0' }} reportHistory={[]} />
      </ThemeProvider>,
    );

    const warning = `${label} · SYNTHETIC-B*, synthetic-a`;
    expect(screen.getByText(warning)).toBeVisible();
    expect(screen.getByLabelText('Гемоглобин')).toHaveAccessibleDescription(expect.stringContaining(warning));
    expect(screen.getByLabelText('SYNTHETIC-NEIGHBOR')).not.toHaveAccessibleDescription(expect.stringContaining(warning));
  });

  it('keeps the clinical assessment separate and drops old codes while the value is edited', () => {
    const editor = (value: string) => (
      <ThemeProvider>
        <ReportEditor {...baseProps} activeInstance={report} draftValues={{ hgb: value, other: '5.0' }} reportHistory={[]} />
      </ThemeProvider>
    );
    const { rerender } = render(editor('5.0'));

    expect(screen.getAllByText('норма')).toHaveLength(2);
    expect(screen.getByText(/Предупреждения анализатора/)).toBeVisible();
    rerender(editor('7.0'));
    expect(screen.getByText('черновик')).toBeVisible();
    expect(screen.queryByText(/Предупреждения анализатора/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Гемоглобин')).not.toHaveAccessibleDescription(expect.stringContaining('SYNTHETIC-B*'));
  });

  it('keeps codes for an accepted equivalent decimal spelling', () => {
    const value = '5,00';
    const numericField = { ...field, result_kind: 'numeric', value_numeric: 5 };
    const numericReport = { ...report, sections: [{ ...section, fields: [numericField] }] };
    const accepted = readReportDraft(numericReport, { values: { hgb: value }, signer: {}, studyDate: '' });
    expect(accepted.values.hgb).toBe(value);
    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} activeInstance={numericReport} draftValues={{ hgb: value }}
          acceptedValues={accepted.values} reportHistory={[]} />
      </ThemeProvider>,
    );

    expect(screen.getByText('Предупреждения анализатора · SYNTHETIC-B*, synthetic-a')).toBeVisible();
  });

  it('shows codes for a matching saved absence and hides them when its reason is edited', () => {
    const absenceReason = 'SYNTHETIC-ABSENCE';
    const absentField = { ...field, value_text: '', result_kind: 'absent', absence_reason: absenceReason };
    const editor = (reason: string) => (
      <ThemeProvider>
        <ReportEditor {...baseProps} activeInstance={{ ...report, sections: [{ ...section, fields: [absentField] }] }}
          draftValues={{ hgb: '', hgb__absence_reason: reason }} reportHistory={[]} />
      </ThemeProvider>
    );
    const { rerender } = render(editor(absenceReason));

    expect(screen.getByText('Предупреждения анализатора · SYNTHETIC-B*, synthetic-a')).toBeVisible();
    rerender(editor('SYNTHETIC-REVISED-ABSENCE'));
    expect(screen.queryByText(/Предупреждения анализатора/)).not.toBeInTheDocument();
  });

  it.each([['omitted', undefined], ['empty', []]])('omits the indicator when instrument codes are %s', (_condition, codes) => {
    const fieldWithoutCodes = { ...field, instrument_flags: codes };
    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} activeInstance={{ ...report, sections: [{ ...section, fields: [fieldWithoutCodes] }] }}
          draftValues={{ hgb: '5.0' }} reportHistory={[]} />
      </ThemeProvider>,
    );

    expect(screen.queryByText(/Предупреждения анализатора/)).not.toBeInTheDocument();
  });
});
