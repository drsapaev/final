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
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

vi.mock('./hooks/useLabToast', () => ({
  useLabToast: () => ({
    interactiveInfo: vi.fn(),
    interactiveWarning: vi.fn(),
    interactiveError: vi.fn(),
  }),
}));

import ReportEditorRaw from '../ReportEditor';

const ReportEditor = ReportEditorRaw as unknown as React.ComponentType<Record<string, unknown>>;

const ACTIVE_INSTANCE = {
  id: 91,
  template_id: 3,
  status: 'IN_PROGRESS',
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
          required: true,
        },
      ],
    },
  ],
};

// Real list-API contract: summary DTOs WITHOUT `sections`.
const HISTORY = [
  { id: 91, template_id: 3, created_at: '2026-11-07T10:00:00Z' },
  { id: 90, template_id: 3, created_at: '2026-10-05T10:00:00Z' },
  { id: 80, template_id: 7, created_at: '2026-09-01T10:00:00Z' },
];

const PREV_DETAILS = {
  id: 90,
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
          reportHistory={[{ id: 91, template_id: 3, created_at: '2026-11-07T10:00:00Z' }, { id: 80, template_id: 7, created_at: '2026-09-01T10:00:00Z' }]}
        />
      </ThemeProvider>
    );

    await new Promise((resolve) => { setTimeout(resolve, 80); });
    expect(getInstanceMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/↗/)).toBeNull();
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
