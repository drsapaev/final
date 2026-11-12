/**
 * RETRO-3921-01 (consolidated post-merge review of #3921, PR #3944) —
 * fail-first, full chain.
 *
 * The direct-print path of #3921 correctly stopped the PDF fallback for a
 * malformed 2xx ACK (ambiguous), but its catch in printLabResults returned
 * ambiguous:false for EVERY rejection — including a client timeout or a
 * lost response AFTER the server had accepted and queued the physical job.
 * handlePrint treated ambiguous:false as a definite failure and
 * automatically opened the PDF fallback: the operator got a second print
 * route for a job that may already be queued, with the report audit state
 * unconfirmed.
 *
 * This suite runs the REAL printService (only the axios layer is mocked):
 *  - a lost transport ACK (client timeout, no server response) resolves
 *    ambiguous → the workbench shows the unconfirmed warning and never
 *    opens the PDF fallback nor marks the report printed;
 *  - a server-RETURNED refusal stays a definite failure → the
 *    operator-driven PDF fallback remains available.
 */
import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LabReportWorkbenchRaw from '../LabReportWorkbench';
import { labReportingApi } from '@/api/labReporting';
import { ThemeProvider } from '@/contexts/ThemeContext';

// The component under test still relies on TS prop types (see the main
// workbench suite for the rationale behind this cast).
const LabReportWorkbench = LabReportWorkbenchRaw as unknown as React.ComponentType<Record<string, unknown>>;

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
  },
}));

// Keep the real api/client module surface (interceptors, token helpers),
// replace ONLY api.post — the transport the real printService uses.
vi.mock('../../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/client')>();
  return {
    ...actual,
    api: {
      ...(actual.api as unknown as Record<string, unknown>),
      post: vi.fn(),
    },
  };
});

import { api } from '../../../api/client';

const apiPost = api.post as unknown as ReturnType<typeof vi.fn>;
const mockedApi = labReportingApi as unknown as {
  downloadPdf: ReturnType<typeof vi.fn>;
  markPrinted: ReturnType<typeof vi.fn>;
};

const finalizedPrintableInstance = {
  id: 905,
  status: 'FINALIZED',
  template_id: 3,
  patient_id: 444,
  updated_at: '2026-11-09T08:00:00.123456+00:00',
  signer_snapshot: {},
  available_actions: ['print'],
  critical_findings: [],
  sections: [
    {
      key: 'cbc',
      title: 'CBC',
      fields: [
        { field_key: 'wbc', label: 'Лейкоциты', value_type: 'text', value_text: '5.2', comment: null },
      ],
    },
  ],
};

function renderPrintable() {
  return render(
    <ThemeProvider>
      <LabReportWorkbench
        selectedAppointment={null}
        templates={[]}
        templateResolution={null}
        templateResolutionLoading={false}
        reportHistory={[]}
        recentReports={[]}
        activeInstance={finalizedPrintableInstance}
        onInstanceChange={vi.fn()}
        onOpenInstance={vi.fn()}
        onRefreshHistory={vi.fn()}
        onRefreshRecentReports={vi.fn()}
        onQueueChanged={vi.fn()}
        notify={vi.fn()}
      />
    </ThemeProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  });
});

describe('RETRO-3921-01: a lost print-job ACK never opens a second print route', () => {
  it('client timeout after the server may have queued the job → warning, no PDF fallback, no markPrinted', async () => {
    // The server accepted the job but the client timed out waiting for the
    // ACK (axios ECONNABORTED, no response object).
    apiPost.mockRejectedValueOnce(
      Object.assign(new Error('timeout of 15000ms exceeded'), { code: 'ECONNABORTED' }),
    );
    mockedApi.downloadPdf.mockReset();
    mockedApi.markPrinted.mockReset();

    renderPrintable();

    fireEvent.click(screen.getByRole('button', { name: 'Печать результата' }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    await act(async () => {
      for (let i = 0; i < 8; i += 1) await Promise.resolve();
    });

    // The job's fate is UNKNOWN: no duplicate route, no blind status write.
    expect(mockedApi.downloadPdf).not.toHaveBeenCalled();
    expect(mockedApi.markPrinted).not.toHaveBeenCalled();
    // The operator is told to check the printer/queue instead.
    expect(screen.getByText(/не подтверждён/i)).toBeInTheDocument();
  });

  it('server-RETURNED refusal stays a definite failure — the operator PDF fallback remains available', async () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue({} as Window);
    try {
      // The print service itself answered 502: the job was NOT queued.
      apiPost.mockRejectedValueOnce({
        response: { status: 502, data: { detail: 'print backend unavailable' } },
      });
      mockedApi.downloadPdf.mockReset().mockResolvedValue(new Blob(['%PDF-synthetic'], { type: 'application/pdf' }));
      mockedApi.markPrinted.mockReset();

      renderPrintable();

      fireEvent.click(screen.getByRole('button', { name: 'Печать результата' }));
      await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
      await act(async () => {
        for (let i = 0; i < 8; i += 1) await Promise.resolve();
      });

      // Definite refusal → the operator-driven fallback PREPARES the PDF…
      await waitFor(() => {
        expect(mockedApi.downloadPdf).toHaveBeenCalledTimes(1);
      });
      // …but RETRO-3970-01: the failed print attempt never AUTO-opens a tab
      // (a noopener window.open returns null even on success — the old
      // truthiness gate was a lie). The explicit follow-up click appears.
      expect(windowOpenSpy).not.toHaveBeenCalled();
      expect(screen.getByRole('button', { name: 'Открыть PDF для печати' })).toBeInTheDocument();
      // …and the report is NOT marked printed by merely preparing/opening
      // the PDF (LABPRINT-FE-002 stays intact).
      expect(mockedApi.markPrinted).not.toHaveBeenCalled();
    } finally {
      windowOpenSpy.mockRestore();
    }
  });
});
