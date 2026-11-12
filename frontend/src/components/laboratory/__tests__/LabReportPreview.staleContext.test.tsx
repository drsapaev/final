/**
 * LABR-FE-002 (audit 3886, ledger group «lab report API, PDF preview and
 * AI result ownership») — fail-first regression for the preview ownership:
 *
 * `handlePreviewPdf` awaited `previewInstancePdf(A)` and unconditionally
 * created the object URL, opened the popup and wrote shared feedback —
 * a late A preview resolved after the operator switched to report/patient
 * B opened A's PDF over B's screen.
 *
 * Red-first: on the pre-fix source the stale A blob opens a window and
 * stamps A's success feedback into B's workbench.
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

import { labReportingApi } from '@/api/labReporting';
import LabReportWorkbenchRaw from '../LabReportWorkbench';

const LabReportWorkbench = LabReportWorkbenchRaw as unknown as React.ComponentType<
  Record<string, unknown>
>;

const INSTANCE_A = {
  id: 91,
  status: 'IN_PROGRESS',
  template_id: 3,
  patient_id: 444,
  updated_at: '2026-09-25T08:00:00.123456+00:00',
  signer_snapshot: {},
  available_actions: ['edit', 'save_draft', 'finalize', 'preview'],
  can_preview: true,
  critical_findings: [],
  sections: [
    { key: 'cbc', title: 'CBC', fields: [{ field_key: 'hgb', label: 'Гемоглобин', value_type: 'numeric', value_text: '140', comment: null }] },
  ],
};

const INSTANCE_B = {
  ...INSTANCE_A,
  id: 92,
  patient_id: 555,
};

const CONTEXT_A = { epoch: 1, selectionKey: 'A', patientId: 444 };
const CONTEXT_B = { epoch: 2, selectionKey: 'B', patientId: 555 };

const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;

// RETRO-3970-01: честная резервация контекста — window.open('', '_blank')
// БЕЗ feature-строки: успех возвращает Window (truthy), реальный блок —
// null. Моделирует браузерный контракт patientFilePreview.ts (CARDHIST-FE-001).
function makeReservedWindow(): Window {
  return {
    close: vi.fn(),
    opener: 'initiator' as unknown,
    location: { href: '' },
  } as unknown as Window;
}


function workbenchProps(activeInstance: typeof INSTANCE_A, getOperationContext: () => unknown) {
  return ({
    selectedAppointment: null,
    templates: [],
    templateResolution: null,
    templateResolutionLoading: false,
    reportHistory: [],
    recentReports: [],
    activeInstance,
    onInstanceChange: vi.fn(),
    onOpenInstance: vi.fn(),
    onRefreshHistory: vi.fn(),
    onRefreshRecentReports: vi.fn(),
    onQueueChanged: vi.fn(),
    notify: vi.fn(),
    getOperationContext,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(URL, 'createObjectURL', {
    writable: true,
    configurable: true,
    value: vi.fn(() => 'blob:lab-preview'),
  });
  Object.defineProperty(URL, 'revokeObjectURL', {
    writable: true,
    configurable: true,
    value: vi.fn(),
  });
  vi.spyOn(window, 'open').mockImplementation(() => makeReservedWindow());
});

describe('LABR-FE-002 — a late preview is owned by its initiating context', () => {
  it('drops the stale A preview after the operator switched to report B (pre-fix: A\'s PDF opened over B)', async () => {
    let releasePreview: (mode: 'blob' | 'reject') => void = () => {
      throw new Error('preview release not armed');
    };
    mockedApi.previewInstancePdf.mockImplementation(() => new Promise((resolve, reject) => {
      releasePreview = (mode) => {
        if (mode === 'reject') {
          reject(new Error('preview failed'));
        } else {
          resolve(new Blob(['%PDF-synthetic-A'], { type: 'application/pdf' }));
        }
      };
    }));

    const { rerender } = render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(INSTANCE_A, () => CONTEXT_A)} />
      </ThemeProvider>
    );

    // The A preview starts and hangs.
    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));
    await waitFor(() => expect(mockedApi.previewInstancePdf).toHaveBeenCalledWith(91));

    // The operator switches to report B while the read is pending.
    rerender(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(INSTANCE_B, () => CONTEXT_B)} />
      </ThemeProvider>
    );

    // A's blob resolves late.
    releasePreview('blob');
    await new Promise((resolve) => { setTimeout(resolve, 120); });

    // The reservation WAS made synchronously in the gesture, but the stale
    // settle must CLOSE the reserved tab and never navigate it: no object
    // URL created, no success feedback stamped into B's workbench, no print
    // side effects.
    expect(window.open).toHaveBeenCalledTimes(1);
    expect((window.open as unknown as ReturnType<typeof vi.fn>).mock.calls[0]).toEqual(['', '_blank']);
    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      location: { href: string };
    };
    expect(reserved.close).toHaveBeenCalledTimes(1);
    expect(reserved.location.href).toBe('');
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(mockedApi.markPrinted).not.toHaveBeenCalled();
  });

  it('drops the stale A preview failure after the operator switched to report B', async () => {
    let releasePreview: (mode: 'blob' | 'reject') => void = () => {
      throw new Error('preview release not armed');
    };
    mockedApi.previewInstancePdf.mockImplementation(() => new Promise((resolve, reject) => {
      releasePreview = (mode) => {
        if (mode === 'reject') {
          reject(new Error('preview failed'));
        } else {
          resolve(new Blob(['%PDF-synthetic-A'], { type: 'application/pdf' }));
        }
      };
    }));

    const notify = vi.fn();
    const propsA = { ...workbenchProps(INSTANCE_A, () => CONTEXT_A), notify };
    const { rerender } = render(
      <ThemeProvider>
        <LabReportWorkbench {...propsA} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));
    await waitFor(() => expect(mockedApi.previewInstancePdf).toHaveBeenCalledWith(91));

    rerender(
      <ThemeProvider>
        <LabReportWorkbench {...{ ...workbenchProps(INSTANCE_B, () => CONTEXT_B), notify }} />
      </ThemeProvider>
    );

    releasePreview('reject');
    await new Promise((resolve) => { setTimeout(resolve, 120); });

    // The stale failure must not surface as B's error toast, and the
    // reserved blank tab must be closed, not left behind (RETRO-3970-01).
    expect(notify).not.toHaveBeenCalled();
    expect(mockedApi.markPrinted).not.toHaveBeenCalled();
    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      location: { href: string };
    };
    expect(reserved.close).toHaveBeenCalledTimes(1);
    expect(reserved.location.href).toBe('');
  });

  it('control: the current context\'s preview still opens the popup exactly once', async () => {
    mockedApi.previewInstancePdf.mockResolvedValue(
      new Blob(['%PDF-synthetic-current'], { type: 'application/pdf' })
    );

    render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(INSTANCE_A, () => CONTEXT_A)} />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));

    await waitFor(() => {
      expect((window.open as unknown as ReturnType<typeof vi.fn>).mock.calls[0]).toEqual(['', '_blank']);
    }, { timeout: 2500 });
    // RETRO-3970-01: the current context's preview NAVIGATES the reserved
    // tab to the blob URL (opener severed first) and never reports blocked.
    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      opener: unknown;
      location: { href: string };
    };
    expect(reserved.location.href).toBe('blob:lab-preview');
    expect(reserved.opener).toBeNull();
    expect(reserved.close).not.toHaveBeenCalled();
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(mockedApi.markPrinted).not.toHaveBeenCalled();
  });
});

describe('LABR-FE-003 — a stale preview\'s finally must not clear a newer action\'s busy flag', () => {
  // Post-merge review of #3909 (P2): the preview finally checks ONLY the
  // preview epoch, while the try/catch ownership check also compares the
  // live operation context. A preview launched in context A that settles
  // after the operator switched to B (and started a NEWER report action
  // there) still owns the preview epoch — its finally cleared the newer
  // action's busy indicator.
  const INSTANCE_A_REVISE = {
    ...INSTANCE_A,
    available_actions: ['edit', 'save_draft', 'finalize', 'preview', 'revise'],
  };
  const INSTANCE_B_REVISE = {
    ...INSTANCE_A_REVISE,
    id: 92,
    patient_id: 555,
  };

  it('the stale A preview does not reset the newer revise action\'s busy state (pre-fix: epoch-only finally clobbered it)', async () => {
    let releasePreview: (mode: 'blob' | 'reject') => void = () => {
      throw new Error('preview release not armed');
    };
    let releaseRevise: () => void = () => {
      throw new Error('revise release not armed');
    };
    mockedApi.previewInstancePdf.mockImplementation(() => new Promise((resolve, reject) => {
      releasePreview = (mode) => {
        if (mode === 'reject') {
          reject(new Error('preview failed'));
        } else {
          resolve(new Blob(['%PDF-synthetic-A'], { type: 'application/pdf' }));
        }
      };
    }));
    mockedApi.revise.mockImplementation(() => new Promise((resolve) => {
      releaseRevise = () => resolve({ id: 93, status: 'IN_PROGRESS', patient_id: 555 });
    }));

    const { rerender } = render(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(INSTANCE_A_REVISE, () => CONTEXT_A)} />
      </ThemeProvider>
    );

    // The A preview starts and hangs (busyAction = 'preview').
    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));
    await waitFor(() => expect(mockedApi.previewInstancePdf).toHaveBeenCalledWith(91));

    // The operator switches to report B while the preview read is pending.
    rerender(
      <ThemeProvider>
        <LabReportWorkbench {...workbenchProps(INSTANCE_B_REVISE, () => CONTEXT_B)} />
      </ThemeProvider>
    );

    // A NEWER report action starts in context B: revise (its confirm
    // resolves, then the revise request hangs — busyAction = 'revise').
    fireEvent.click(screen.getByRole('button', { name: /Исправленная версия/ }));
    const confirmButton = await screen.findByRole('button', { name: 'Создать версию' });
    fireEvent.click(confirmButton);
    await waitFor(() => expect(mockedApi.revise).toHaveBeenCalledWith(92));

    // The revise action is visibly busy on the actions bar.
    expect(screen.getByRole('button', { name: /Создаю…/ })).toBeInTheDocument();

    // The stale A preview settles now: its body must be dropped (try-guard)
    // AND its finally must not clear the newer action's busy flag.
    releasePreview('blob');
    await new Promise((resolve) => { setTimeout(resolve, 120); });

    // Pre-fix: the epoch-only finally reset busyAction here and the revise
    // button fell back to its idle label while the revise was still busy.
    expect(screen.getByRole('button', { name: /Создаю…/ })).toBeInTheDocument();

    // Cleanup: let the revise settle so no promise stays pending.
    releaseRevise();
    await new Promise((resolve) => { setTimeout(resolve, 120); });
  });
});
