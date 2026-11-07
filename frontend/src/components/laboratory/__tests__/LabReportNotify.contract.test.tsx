/**
 * LABN-FE-001 + LABN-FE-002 (audit 3886, ledger group «report history and
 * Telegram result notification contract») — fail-first regressions for the
 * workbench notify action:
 *
 * LABN-FE-001: the pre-fix handler posted {patient_id, instance_id} JSON to
 * the legacy /telegram/send-lab-results route — a lab_result-scoped route
 * with query-parameter validation that rejects the shape with 422 before
 * business logic and never implements the promised PDF delivery. The fix
 * calls the dedicated instance-scoped route with an explicit
 * {patient_id, report_instance_id} body.
 *
 * LABN-FE-002: the pre-fix handler ignored the response payload and showed
 * the «отправлено» confirmation for ANY resolved HTTP promise. The route
 * answers 200 + {success:false} when the patient is not linked to the bot
 * or disabled lab notifications — that must surface as an honest failure,
 * and a malformed/absent payload must never produce false success.
 *
 * Red-first: on the pre-fix source the endpoint assertion fails (legacy
 * URL + instance_id field) and the success:false / malformed cases show
 * the success confirmation.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

vi.mock('../../../api/labReporting', () => ({
  labReportingApi: {
    getInstance: vi.fn(),
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    finalize: vi.fn(),
    revise: vi.fn(),
    downloadPdf: vi.fn(),
    markPrinted: vi.fn(),
    previewInstancePdf: vi.fn(),
    previewTemplateVersionPdf: vi.fn(),
  },
}));

vi.mock('../../../api/client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../../common/ConfirmDialog', () => ({
  useConfirm: () => [() => Promise.resolve(true), null],
}));

import { api } from '@/api/client';
import LabReportWorkbenchRaw from '../LabReportWorkbench';

const LabReportWorkbench = LabReportWorkbenchRaw as unknown as React.ComponentType<
  Record<string, unknown>
>;

const FINALIZED_INSTANCE = {
  id: 91,
  status: 'FINALIZED',
  template_id: 3,
  patient_id: 444,
  updated_at: '2026-11-05T08:00:00.123456+00:00',
  signer_snapshot: {},
  available_actions: [],
  can_preview: false,
  critical_findings: [],
  sections: [
    { key: 'cbc', title: 'CBC', fields: [{ field_key: 'hgb', label: 'Гемоглобин', value_type: 'numeric', value_text: '140', comment: null }] },
  ],
};

const CONTEXT = { epoch: 1, selectionKey: 'A', patientId: 444 };

const mockedApiPost = api.post as unknown as ReturnType<typeof vi.fn>;

function workbenchProps(notify: (severity: string, message: string) => void) {
  return ({
    selectedAppointment: null,
    templates: [],
    templateResolution: null,
    templateResolutionLoading: false,
    reportHistory: [],
    recentReports: [],
    activeInstance: FINALIZED_INSTANCE,
    onInstanceChange: vi.fn(),
    onOpenInstance: vi.fn(),
    onRefreshHistory: vi.fn(),
    onRefreshRecentReports: vi.fn(),
    onQueueChanged: vi.fn(),
    notify,
    getOperationContext: () => CONTEXT,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('LABN-FE-001 — notify targets the instance-scoped report PDF contract', () => {
  it('posts {patient_id, report_instance_id} to /telegram/send-lab-report-instance (pre-fix: legacy /send-lab-results with instance_id)', async () => {
    mockedApiPost.mockResolvedValue({ data: { success: true } });

    render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(vi.fn())} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Отправить пациенту/ }));

    await waitFor(() => expect(mockedApiPost).toHaveBeenCalledTimes(1));
    expect(mockedApiPost).toHaveBeenCalledWith('/telegram/send-lab-report-instance', {
      patient_id: 444,
      report_instance_id: 91,
    });
  });

  it('control: HTTP rejection surfaces as an error, never as success', async () => {
    mockedApiPost.mockRejectedValue(new Error('network down'));

    const notify = vi.fn();
    render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(notify)} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Отправить пациенту/ }));

    await waitFor(() => expect(notify).toHaveBeenCalled());
    expect(notify).not.toHaveBeenCalledWith('success', expect.anything());
  });
});

describe('LABN-FE-002 — a resolved 2xx is success ONLY on explicit success === true', () => {
  it('200 + {success:false} with a server reason shows that reason as an error (pre-fix: «отправлено»)', async () => {
    mockedApiPost.mockResolvedValue({
      data: { success: false, message: 'Пациент не зарегистрирован в Telegram боте' },
    });

    const notify = vi.fn();
    render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(notify)} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Отправить пациенту/ }));

    await waitFor(() => expect(notify).toHaveBeenCalledTimes(1));
    expect(notify).toHaveBeenCalledWith(
      'error',
      'Пациент не зарегистрирован в Telegram боте'
    );
    expect(notify).not.toHaveBeenCalledWith('success', expect.anything());
  });

  it('200 + {success:false} without a readable message falls back to the honest not-delivered error', async () => {
    mockedApiPost.mockResolvedValue({ data: { success: false } });

    const notify = vi.fn();
    render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(notify)} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Отправить пациенту/ }));

    await waitFor(() => expect(notify).toHaveBeenCalledTimes(1));
    const [severity, message] = notify.mock.calls[0];
    expect(severity).toBe('error');
    expect(String(message)).not.toContain('отправлены');
  });

  it('200 with a malformed/absent payload never produces false success (pre-fix: «отправлено»)', async () => {
    mockedApiPost.mockResolvedValue({ data: undefined });

    const notify = vi.fn();
    render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(notify)} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Отправить пациенту/ }));

    await waitFor(() => expect(notify).toHaveBeenCalledTimes(1));
    expect(notify).not.toHaveBeenCalledWith('success', expect.anything());
    expect(notify.mock.calls[0][0]).toBe('error');
  });

  it('control: 200 + {success:true} shows the success confirmation', async () => {
    mockedApiPost.mockResolvedValue({ data: { success: true } });

    const notify = vi.fn();
    render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(notify)} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Отправить пациенту/ }));

    await waitFor(() =>
      expect(notify).toHaveBeenCalledWith('success', expect.stringContaining('Telegram'))
    );
    expect(notify).not.toHaveBeenCalledWith('error', expect.anything());
  });
});
