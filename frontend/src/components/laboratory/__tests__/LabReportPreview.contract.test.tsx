/**
 * PR8 (codex-lab-workflow-hardening-plan): server-rendered PDF preview.
 *
 * Контракты:
 * 1. ActionsBar: кнопка «Предпросмотр PDF» рендерится только когда backend
 *    разрешил действие ('preview' в available_actions / canPreview).
 * 2. Workbench: preview открывает blob в новой вкладке и НЕ вызывает
 *    markPrinted/finalize/notify — preview без побочных эффектов.
 * 3. PreviewTab (template editor): кнопка серверного PDF-рендера
 *    сохранённой версии шаблона; в tab нет данных пациентов.
 * 4. API-клиент: preview-запросы идут на выделенные preview-маршруты.
 */
import React from 'react';
import '@testing-library/jest-dom';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LabReportActionsBar from '../LabReportActionsBar';
import PreviewTab from '../templateEditor/PreviewTab';
import { labReportingApi } from '@/api/labReporting';
import { hasLabReportAction } from '../utils/labReportActions';
import { ThemeProvider } from '@/contexts/ThemeContext';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../..');
const workbenchSource = fs.readFileSync(
  path.join(ROOT, 'laboratory/LabReportWorkbench.tsx'),
  'utf8'
);
const apiClientSource = fs.readFileSync(
  path.resolve(ROOT, '../api/labReporting.ts'),
  'utf8'
);

// RETRO-3970-01: честная резервация контекста — window.open('', '_blank')
// БЕЗ feature-строки: успех возвращает Window (truthy), реальный блок —
// null. Моделирует браузерный контракт patientFilePreview.ts (CARDHIST-FE-001).
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function makeReservedWindow(): Window {
  return {
    close: vi.fn(),
    opener: 'initiator' as unknown,
    location: { href: '' },
  } as unknown as Window;
}

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

// vi.mock выше хойстится и перехватывает этот импорт — мок API активен.
import LabReportWorkbenchRaw from '../LabReportWorkbench';
const LabReportWorkbench = LabReportWorkbenchRaw as unknown as React.ComponentType<
  Record<string, unknown>
>;

const draftInstanceWithPreview = {
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
    {
      key: 'cbc',
      title: 'CBC',
      fields: [
        {
          field_key: 'hgb',
          label: 'Гемоглобин',
          value_type: 'numeric',
          value_text: '140',
          comment: null,
        },
      ],
    },
  ],
};

const finalizedInstance = {
  ...draftInstanceWithPreview,
  id: 92,
  status: 'FINALIZED',
  available_actions: ['revise', 'print'],
  can_preview: false,
};

describe('PR8: lab PDF preview — ActionsBar', () => {
  it('renders the preview button when backend allows the action', () => {
    const onPreview = vi.fn();
    render(
      <ThemeProvider>
        <LabReportActionsBar
          canSaveDraft
          canFinalize
          canPreview
          onSaveDraft={vi.fn()}
          onFinalize={vi.fn()}
          onRevise={vi.fn()}
          onPrint={vi.fn()}
          onPreview={onPreview}
        />
      </ThemeProvider>
    );
    const button = screen.getByRole('button', { name: /Предпросмотр PDF/ });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onPreview).toHaveBeenCalledTimes(1);
  });

  it('hides the preview button when the action is not allowed', () => {
    render(
      <ThemeProvider>
        <LabReportActionsBar
          canRevise
          canPrint
          onSaveDraft={vi.fn()}
          onFinalize={vi.fn()}
          onRevise={vi.fn()}
          onPrint={vi.fn()}
        />
      </ThemeProvider>
    );
    expect(screen.queryByRole('button', { name: /Предпросмотр PDF/ })).toBeNull();
  });
});

describe('PR8: hasLabReportAction preview resolution (backend SSOT)', () => {
  it('resolves preview from available_actions and can_preview fallback', () => {
    expect(hasLabReportAction(draftInstanceWithPreview, 'preview')).toBe(true);
    expect(
      hasLabReportAction({ can_preview: true } as Record<string, unknown>, 'preview')
    ).toBe(true);
    expect(hasLabReportAction(finalizedInstance, 'preview')).toBe(false);
    expect(hasLabReportAction(null, 'preview')).toBe(false);
  });
});

describe('PR8: workbench preview flow — no side effects', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom не реализует blob-URL API — стабаем для preview-потока.
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

  it('opens the server preview in the reserved tab and never marks the report printed', async () => {
    const mockedApi = labReportingApi as unknown as Record<
      string,
      ReturnType<typeof vi.fn>
    >;
    mockedApi.previewInstancePdf.mockResolvedValue(
      new Blob(['%PDF-synthetic-preview'], { type: 'application/pdf' })
    );

    render(
      <ThemeProvider>
        <LabReportWorkbench
          selectedAppointment={null}
          templates={[]}
          templateResolution={null}
          templateResolutionLoading={false}
          reportHistory={[]}
          recentReports={[]}
          activeInstance={draftInstanceWithPreview}
          onInstanceChange={vi.fn()}
          onOpenInstance={vi.fn()}
          onRefreshHistory={vi.fn()}
          onRefreshRecentReports={vi.fn()}
          onQueueChanged={vi.fn()}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));

    await waitFor(() =>
      expect(mockedApi.previewInstancePdf).toHaveBeenCalledWith(91)
    );
    // Контракт PR8: preview не имеет серверных побочных эффектов.
    expect(mockedApi.markPrinted).not.toHaveBeenCalled();
    expect(mockedApi.finalize).not.toHaveBeenCalled();
    expect(mockedApi.downloadPdf).not.toHaveBeenCalled();
    // RETRO-3970-01: резервация — СИНХРОННЫЙ первый вызов window.open
    // в клике (до сетевого await), без feature-строки; успех резервирует
    // контекст, поэтому «blocked» после успешного open невозможен.
    const openSpy = window.open as unknown as ReturnType<typeof vi.fn>;
    expect(openSpy.mock.calls[0]).toEqual(['', '_blank']);
    expect(openSpy.mock.invocationCallOrder[0]).toBeLessThan(
      mockedApi.previewInstancePdf.mock.invocationCallOrder[0]
    );
    const reserved = openSpy.mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      opener: unknown;
      location: { href: string };
    };
    expect(reserved.location.href).toBe('blob:lab-preview');
    expect(reserved.opener).toBeNull();
    expect(reserved.close).not.toHaveBeenCalled();
    expect(screen.getByText(/открыт в новой вкладке/)).toBeInTheDocument();
    expect(screen.queryByText(/заблокирован/)).toBeNull();
  });

  it('does not offer the preview action for finalized reports', () => {
    render(
      <ThemeProvider>
        <LabReportWorkbench
          selectedAppointment={null}
          templates={[]}
          templateResolution={null}
          templateResolutionLoading={false}
          reportHistory={[]}
          recentReports={[]}
          activeInstance={finalizedInstance}
          onInstanceChange={vi.fn()}
          onOpenInstance={vi.fn()}
          onRefreshHistory={vi.fn()}
          onRefreshRecentReports={vi.fn()}
          onQueueChanged={vi.fn()}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );
    expect(screen.queryByRole('button', { name: /Предпросмотр PDF/ })).toBeNull();
  });

  it('handlePreviewPdf never calls markPrinted (source contract)', () => {
    // Статический пин: обработчик preview не должен содержать вызов
    // markPrinted — статус меняет только реальная печать.
    const handlerStart = workbenchSource.indexOf('async function handlePreviewPdf');
    const handlerEnd = workbenchSource.indexOf('async function handlePrint');
    expect(handlerStart).toBeGreaterThan(-1);
    expect(handlerEnd).toBeGreaterThan(handlerStart);
    const handlerSource = workbenchSource.slice(handlerStart, handlerEnd);
    expect(handlerSource).not.toContain('markPrinted');
    expect(handlerSource).toContain('previewInstancePdf');
  });
});

describe('RETRO-3970-01 — honest popup reservation for the workbench preview', () => {
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

  function renderPreview(activeInstance = draftInstanceWithPreview) {
    return render(
      <ThemeProvider>
        <LabReportWorkbench
          selectedAppointment={null}
          templates={[]}
          templateResolution={null}
          templateResolutionLoading={false}
          reportHistory={[]}
          recentReports={[]}
          activeInstance={activeInstance}
          onInstanceChange={vi.fn()}
          onOpenInstance={vi.fn()}
          onRefreshHistory={vi.fn()}
          onRefreshRecentReports={vi.fn()}
          onQueueChanged={vi.fn()}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );
  }

  it('a genuinely blocked reservation reports blocked WITHOUT any API call', async () => {
    const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;
    (window.open as unknown as ReturnType<typeof vi.fn>).mockReturnValueOnce(null);

    renderPreview();
    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));
    await new Promise((resolve) => { setTimeout(resolve, 60); });

    // True blocked signal: no fetch, no blob, no false success.
    expect(mockedApi.previewInstancePdf).not.toHaveBeenCalled();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(screen.getByText(/заблокировано браузером/)).toBeInTheDocument();
  });

  it('a failed preview read closes the reserved tab with no navigation', async () => {
    const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;
    mockedApi.previewInstancePdf.mockRejectedValue(new Error('preview failed'));

    renderPreview();
    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));
    await waitFor(() => expect(mockedApi.previewInstancePdf).toHaveBeenCalled());
    await new Promise((resolve) => { setTimeout(resolve, 80); });

    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      location: { href: string };
    };
    expect(reserved.close).toHaveBeenCalledTimes(1);
    expect(reserved.location.href).toBe('');
    expect(screen.getByText(/Не удалось сформировать предпросмотр/)).toBeInTheDocument();
  });

  it('a zero-byte preview PDF is rejected like an invalid one — no tab navigation (review P2)', async () => {
    const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;
    mockedApi.previewInstancePdf.mockResolvedValue(new Blob([], { type: 'application/pdf' }));

    renderPreview();
    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));
    await waitFor(() => expect(mockedApi.previewInstancePdf).toHaveBeenCalled());
    await new Promise((resolve) => { setTimeout(resolve, 80); });

    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      location: { href: string };
    };
    expect(reserved.close).toHaveBeenCalledTimes(1);
    expect(reserved.location.href).toBe('');
    expect(screen.getByText(/сформирован некорректно/)).toBeInTheDocument();
  });

  it('an invalid blob closes the reserved tab instead of leaving a blank one', async () => {
    const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;
    mockedApi.previewInstancePdf.mockResolvedValue(null as unknown as Blob);

    renderPreview();
    fireEvent.click(screen.getByRole('button', { name: /Предпросмотр PDF/ }));
    await waitFor(() => expect(mockedApi.previewInstancePdf).toHaveBeenCalled());
    await new Promise((resolve) => { setTimeout(resolve, 80); });

    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      location: { href: string };
    };
    expect(reserved.close).toHaveBeenCalledTimes(1);
    expect(reserved.location.href).toBe('');
    expect(screen.getByText(/сформирован некорректно/)).toBeInTheDocument();
  });
});

describe('PR8: template editor PreviewTab — server PDF preview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(URL, 'createObjectURL', {
      writable: true,
      configurable: true,
      value: vi.fn(() => 'blob:template-preview'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      writable: true,
      configurable: true,
      value: vi.fn(),
    });
    vi.spyOn(window, 'open').mockImplementation(() => makeReservedWindow());
  });

  it('renders the server preview button for the saved draft version', async () => {
    const mockedApi = labReportingApi as unknown as Record<
      string,
      ReturnType<typeof vi.fn>
    >;
    mockedApi.previewTemplateVersionPdf.mockResolvedValue(
      new Blob(['%PDF-synthetic-template'], { type: 'application/pdf' })
    );

    render(
      <ThemeProvider>
        <PreviewTab
          draftVersion={{
            id: 55,
            branding_overrides: { clinic_name: 'Синтетическая клиника' },
            signer_defaults: {},
            sections: [
              {
                title: 'Синтетическая секция',
                fields: [
                  { field_key: 'hgb', label: 'Гемоглобин', unit: 'г/л' },
                ],
              },
            ],
          }}
        />
      </ThemeProvider>
    );

    const button = screen.getByRole('button', { name: /PDF-предпросмотр/ });
    fireEvent.click(button);

    await waitFor(() =>
      expect(mockedApi.previewTemplateVersionPdf).toHaveBeenCalledWith(55)
    );
    // RETRO-3970-01: резервация синхронна и без feature-строки; вкладка
    // заполняется blob-URL уже после валидного ответа.
    const openSpy = window.open as unknown as ReturnType<typeof vi.fn>;
    expect(openSpy.mock.calls[0]).toEqual(['', '_blank']);
    expect(openSpy.mock.invocationCallOrder[0]).toBeLessThan(
      mockedApi.previewTemplateVersionPdf.mock.invocationCallOrder[0]
    );
    const reserved = openSpy.mock.results[0].value as {
      opener: unknown;
      location: { href: string };
    };
    expect(reserved.location.href).toBe('blob:template-preview');
    expect(reserved.opener).toBeNull();
  });

  it('tab contract: no patient props, placeholders only (no real patient data)', () => {
    const previewTabSource = fs.readFileSync(
      path.join(ROOT, 'laboratory/templateEditor/PreviewTab.tsx'),
      'utf8'
    );
    // У таба нет пропа с данными пациента — только структура шаблона.
    expect(previewTabSource).not.toContain('patient_snapshot');
    expect(previewTabSource).not.toContain('patient_id');
    // Серверный preview идёт через выделенный preview-метод API-клиента.
    expect(previewTabSource).toContain('previewTemplateVersionPdf');
  });

  it('a blocked reservation shows a visible error and performs no API call (RETRO-3970-01)', async () => {
    const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;
    (window.open as unknown as ReturnType<typeof vi.fn>).mockReturnValueOnce(null);

    render(
      <ThemeProvider>
        <PreviewTab draftVersion={{ id: 55, sections: [] }} />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: /PDF-предпросмотр/ }));
    await new Promise((resolve) => { setTimeout(resolve, 60); });

    expect(mockedApi.previewTemplateVersionPdf).not.toHaveBeenCalled();
    expect(screen.getByText(/заблокировано браузером/)).toBeInTheDocument();
  });

  it('a zero-byte template preview PDF is rejected like an invalid one (review P2)', async () => {
    const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;
    mockedApi.previewTemplateVersionPdf.mockResolvedValue(new Blob([], { type: 'application/pdf' }));

    render(
      <ThemeProvider>
        <PreviewTab draftVersion={{ id: 55, sections: [] }} />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: /PDF-предпросмотр/ }));
    await waitFor(() => expect(mockedApi.previewTemplateVersionPdf).toHaveBeenCalled());
    await new Promise((resolve) => { setTimeout(resolve, 80); });

    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      location: { href: string };
    };
    expect(reserved.close).toHaveBeenCalledTimes(1);
    expect(reserved.location.href).toBe('');
    expect(screen.getByText(/сформирован некорректно/)).toBeInTheDocument();
  });

  it('an in-flight template preview does not navigate its reserved tab after unmount (review P2)', async () => {
    const gateBlob = deferred<Blob>();
    const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;
    mockedApi.previewTemplateVersionPdf.mockImplementation(() => gateBlob.promise);

    const { unmount } = render(
      <ThemeProvider>
        <PreviewTab draftVersion={{ id: 55, sections: [] }} />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: /PDF-предпросмотр/ }));
    await waitFor(() => expect(mockedApi.previewTemplateVersionPdf).toHaveBeenCalled());
    unmount();
    await act(async () => {
      gateBlob.resolve(new Blob(['%PDF-late'], { type: 'application/pdf' }));
      await new Promise((resolve) => { setTimeout(resolve, 40); });
    });

    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      location: { href: string };
    };
    expect(reserved.close).toHaveBeenCalled();
    expect(reserved.location.href).toBe('');
  });

  it('a failed template preview read closes the reserved blank tab (RETRO-3970-01)', async () => {
    const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;
    mockedApi.previewTemplateVersionPdf.mockRejectedValue(new Error('preview failed'));

    render(
      <ThemeProvider>
        <PreviewTab draftVersion={{ id: 55, sections: [] }} />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: /PDF-предпросмотр/ }));
    await waitFor(() => expect(mockedApi.previewTemplateVersionPdf).toHaveBeenCalled());
    await new Promise((resolve) => { setTimeout(resolve, 80); });

    const reserved = (window.open as unknown as ReturnType<typeof vi.fn>).mock.results[0].value as {
      close: ReturnType<typeof vi.fn>;
      location: { href: string };
    };
    expect(reserved.close).toHaveBeenCalledTimes(1);
    expect(reserved.location.href).toBe('');
    expect(screen.getByText(/Не удалось сформировать PDF-предпросмотр/)).toBeInTheDocument();
  });
});

describe('PR8: API client preview routes', () => {
  it('preview requests target dedicated preview endpoints', () => {
    expect(apiClientSource).toContain(
      '/lab/report-instances/${instanceId}/preview'
    );
    expect(apiClientSource).toContain(
      '/lab/template-versions/${versionId}/preview'
    );
    // Preview — отдельный метод, не переиспользование downloadPdf.
    expect(apiClientSource).toContain('previewInstancePdf');
    expect(apiClientSource).toContain('previewTemplateVersionPdf');
  });
});
