import React from 'react';
import '@testing-library/jest-dom';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import LabReportWorkbenchRaw from '../LabReportWorkbench';
import { labReportingApi } from '@/api/labReporting';
import { printService } from '@/services/print';
import { ThemeProvider } from '@/contexts/ThemeContext';

// The component under test still relies on TS prop types,
// so the inferred prop types collapse to `never`/`undefined` defaults under
// strictNullChecks. Cast to a permissive ComponentType to keep the test
// type-checking without changing runtime behavior.
const LabReportWorkbench = LabReportWorkbenchRaw as unknown as React.ComponentType<Record<string, unknown>>;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workbenchPath = path.resolve(__dirname, '../LabReportWorkbench.tsx');

vi.mock('../../../api/labReporting', () => ({
  labReportingApi: {
    getInstance: vi.fn(),
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    // L-1 fix: markReady removed — endpoint was dead code (WF-round5).
    finalize: vi.fn(),
    revise: vi.fn(),
    downloadPdf: vi.fn(),
    markPrinted: vi.fn(),
  },
}));

vi.mock('../../../services/print', () => ({
  printService: {
    printLabResults: vi.fn(),
  },
}));

describe('LabReportWorkbench', () => {
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

  it('shows recent reports in a fresh lab session and opens the selected form', () => {
    const onOpenInstance = vi.fn();

    render(
              <ThemeProvider>
          <LabReportWorkbench
            selectedAppointment={null}
            templates={[]}
            templateResolution={null}
            templateResolutionLoading={false}
            reportHistory={[]}
            recentReports={[
              {
                id: 22,
                patient_id: 444,
                visit_id: 728,
                created_at: '2026-03-21T07:28:20.000Z',
                status: 'PRINTED',
                patient_snapshot: { full_name: 'Тестовый Пациент Регистратура' },
                template: { name: 'ОАК' },
                flagged_findings_count: 0,
                critical_findings_count: 0,
                max_flag_severity: 0,
              },
            ]}
            activeInstance={null}
            onInstanceChange={vi.fn()}
            onOpenInstance={onOpenInstance}
            onRefreshHistory={vi.fn()}
            onRefreshRecentReports={vi.fn()}
            onQueueChanged={vi.fn()}
            notify={vi.fn()}
          />
        </ThemeProvider>
    );

    expect(
      screen.getByText((content) =>
        content.includes('Выберите пациента из очереди или откройте уже существующий лабораторный отчёт')
      )
    ).toBeInTheDocument();
    expect(screen.getByText('Недавние лабораторные отчёты')).toBeInTheDocument();
    expect(screen.getByText(/Тестовый Пациент Регистратура/i)).toBeInTheDocument();

    const reportButton = screen.getByText('ОАК').closest('button') as HTMLButtonElement;
    expect(reportButton).not.toBeNull();
    fireEvent.click(reportButton);

    expect(onOpenInstance).toHaveBeenCalledWith(22);
  });

  it('uses backend-provided action availability instead of local finalized status rules', () => {
    const source = fs.readFileSync(workbenchPath, 'utf8');

    // P-04 fix: hasLabReportAction вынесена в utils/labReportActions.js.
    // Проверяем, что основной файл импортирует её оттуда и использует.
    // STRAT#1: проверка canEdit/canFinalize/canRevise теперь делегирована
    // в useLabReportState hook, поэтому ищем либо в основном файле, либо
    // в хуке.
    expect(source).toContain('hasLabReportAction');
    expect(source).toContain('from \'./utils/labReportActions\'');

    const hookPath = path.resolve(__dirname, '../hooks/useLabReportState.ts');
    const hookSource = fs.readFileSync(hookPath, 'utf8');

    // Action availability flags должны быть EITHER в workbench OR в hook
    const actionFlags = [
      'const canEditActiveInstance = hasLabReportAction(activeInstance, \'edit\')',
      'const canFinalize = hasLabReportAction(activeInstance, \'finalize\')',
      'const canRevise = hasLabReportAction(activeInstance, \'revise\')',
    ];
    for (const flag of actionFlags) {
      const inWorkbench = source.includes(flag);
      const inHook = hookSource.includes(flag);
      expect(inWorkbench || inHook).toBe(true);
    }

    // SSOT-контракт: никаких status-стрингов в условиях видимости действий
    expect(source).not.toContain('activeInstance.status !== \'FINALIZED\' && activeInstance.status !== \'PRINTED\'');
    expect(source).not.toContain('activeInstance.status === \'FINALIZED\' || activeInstance.status === \'PRINTED\'');
  });

  it('does not invent draft status in the print payload when backend status is missing', () => {
    // P-04 fix: buildLabPrintPayload вынесена в utils/labReportNormalize.js.
    // Проверяем там, что status берётся как есть, без fallback на 'DRAFT'.
    const normalizePath = path.resolve(__dirname, '../utils/labReportNormalize.ts');
    const source = fs.readFileSync(normalizePath, 'utf8');

    expect(source).toContain('status: instance?.status || null');
    expect(source).not.toContain('status: instance?.status || \'DRAFT\'');
  });

  it('does not auto-create or auto-open a report when exactly one template is allowed', async () => {
    const onOpenInstance = vi.fn();
    const notify = vi.fn();

    render(
              <ThemeProvider>
          <LabReportWorkbench
            selectedAppointment={{
              id: 17,
              patient_id: 444,
              visit_id: 728,
              patient_fio: 'Test Patient',
              service_codes: ['CBC'],
              service_details: [{ id: 5, code: 'CBC', name: 'CBC' }],
            }}
            templates={[
              {
                id: 3,
                name: 'CBC template',
                family: 'hematology',
                published_version_id: 33,
              },
            ]}
            templateResolution={{
              visit_id: 728,
              service_codes: ['CBC'],
              default_template: {
                id: 3,
                name: 'CBC template',
                family: 'hematology',
                published_version_id: 33,
              },
              allowed_templates: [
                {
                  id: 3,
                  name: 'CBC template',
                  family: 'hematology',
                  published_version_id: 33,
                },
              ],
              unmapped_service_codes: [],
            }}
            templateResolutionLoading={false}
            reportHistory={[]}
            recentReports={[]}
            activeInstance={null}
            onInstanceChange={vi.fn()}
            onOpenInstance={onOpenInstance}
            onRefreshHistory={vi.fn()}
            onRefreshRecentReports={vi.fn()}
            onQueueChanged={vi.fn()}
            notify={notify}
          />
        </ThemeProvider>
    );

    await screen.findByText((content) =>
      content.includes('Единственный допустимый отчёт найден')
    );
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(labReportingApi.createInstance).not.toHaveBeenCalled();
    expect(onOpenInstance).not.toHaveBeenCalled();
    expect(notify).not.toHaveBeenCalledWith(
      'success',
      expect.stringContaining('автоматически')
    );
  });

  it('does not auto-select a service-scoped template unless backend provides default_template', async () => {
    render(
              <ThemeProvider>
          <LabReportWorkbench
            selectedAppointment={{
              id: 17,
              patient_id: 444,
              visit_id: 728,
              patient_fio: 'Test Patient',
              service_codes: ['CBC'],
              service_details: [{ id: 5, code: 'CBC', name: 'CBC' }],
            }}
            templates={[
              {
                id: 3,
                name: 'CBC template',
                family: 'hematology',
                published_version_id: 33,
              },
            ]}
            templateResolution={{
              visit_id: 728,
              service_codes: ['CBC'],
              default_template: null,
              allowed_templates: [
                {
                  id: 3,
                  name: 'CBC template',
                  family: 'hematology',
                  published_version_id: 33,
                },
              ],
              unmapped_service_codes: [],
            }}
            templateResolutionLoading={false}
            reportHistory={[]}
            recentReports={[]}
            activeInstance={null}
            onInstanceChange={vi.fn()}
            onOpenInstance={vi.fn()}
            onRefreshHistory={vi.fn()}
            onRefreshRecentReports={vi.fn()}
            onQueueChanged={vi.fn()}
            notify={vi.fn()}
          />
        </ThemeProvider>
    );

    expect(screen.getByRole('combobox')).toHaveValue('');
    expect(screen.getByRole('combobox').closest('div')?.querySelector('button')).toBeDisabled();
    expect(labReportingApi.createInstance).not.toHaveBeenCalled();
  });

  it('UX-AUDIT-QW1: requires confirm dialog before sending results to patient via Telegram', () => {
    // QW1 fix: handleNotifyPatient — необратимая отправка в Telegram.
    // Должен вызывать useConfirm() перед POST /telegram/send-lab-results.
    const source = fs.readFileSync(workbenchPath, 'utf8');

    // Ищем функцию handleNotifyPatient и проверяем, что она вызывает confirm()
    const fnStart = source.indexOf('async function handleNotifyPatient()');
    expect(fnStart).toBeGreaterThan(-1);
    const fnEnd = source.indexOf('\n  }', fnStart);
    const fnBody = source.slice(fnStart, fnEnd);

    expect(fnBody).toContain('await confirm(');
    // STRAT#9: строка мигрирована на t('confirm.notify_title')
    expect(fnBody).toContain("t('confirm.notify_title')");
    expect(fnBody).toContain("intent: 'warning'");
    // Действие не должно выполняться без подтверждения
    expect(fnBody).toContain('if (!ok) return;');
    // Не должен быть POST до confirm
    const postIndex = fnBody.indexOf("api.post('/telegram/send-lab-results'");
    const confirmIndex = fnBody.indexOf('await confirm(');
    expect(postIndex).toBeGreaterThan(confirmIndex);
  });

  it('UX-AUDIT-FIX8: signer fields are collapsed in <details> by default', () => {
    // FIX8: 4 signer input fields (lab_technician_label/name,
    // approver_label/name) ранее всегда занимали vertical space.
    // Теперь свёрнуты в <details> с auto-expand когда отчёт нередактируем.
    const source = fs.readFileSync(workbenchPath, 'utf8');

    // Должен быть <details> с подсказкой "Подписи"
    expect(source).toContain('<details open={!canEditActiveInstance}>');
    expect(source).toContain('Подписи');
    // Подсказка "только для чтения" когда не editable
    expect(source).toContain('только для чтения — отчёт утверждён');
    // Все 4 signer поля внутри details
    expect(source).toContain("'lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'");
  });

  it('STRAT#9: all 3 confirm dialogs use t() from unified i18n', () => {
    // STRAT#9: finalize, revise, notify dialogs мигрированы на t()
    // i18n-unification: now uses unified useTranslation hook
    const source = fs.readFileSync(workbenchPath, 'utf8');

    // Import
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('useTranslation');

    // Finalize dialog
    expect(source).toContain("t('confirm.finalize_title')");
    expect(source).toContain("t('confirm.finalize_message')");
    expect(source).toContain("t('confirm.finalize_description')");
    expect(source).toContain("t('confirm.finalize_confirm')");

    // Revise dialog
    expect(source).toContain("t('confirm.revise_title')");
    expect(source).toContain("t('confirm.revise_message')");
    expect(source).toContain("t('confirm.revise_description')");
    expect(source).toContain("t('confirm.revise_confirm')");

    // Notify dialog
    expect(source).toContain("t('confirm.notify_title')");
    expect(source).toContain("t('confirm.notify_message')");
    expect(source).toContain("t('confirm.notify_description')");
    expect(source).toContain("t('confirm.notify_confirm')");

    // Все dialogs используют общий cancel label
    expect(source).toContain("t('confirm.cancel')");

    // Больше нет хардкоженных русских строк в confirm() calls
    expect(source).not.toContain("title: 'Утверждение отчёта'");
    expect(source).not.toContain("title: 'Создание исправленной версии'");
    expect(source).not.toContain("title: 'Отправка результатов пациенту'");
    expect(source).not.toContain("confirmLabel: 'Утвердить'");
    expect(source).not.toContain("confirmLabel: 'Создать версию'");
    expect(source).not.toContain("confirmLabel: 'Отправить'");
    expect(source).not.toContain("cancelLabel: 'Отмена'");
  });

  it('STRAT#13: notify() calls use t() for all hardcoded Russian messages', () => {
    // STRAT#13: все notify() с hardcoded русскими строками мигрированы на t()
    const source = fs.readFileSync(workbenchPath, 'utf8');

    // Success messages
    expect(source).toContain("t('success.report_created')");
    expect(source).toContain("t('success.draft_saved')");
    expect(source).toContain("t('success.draft_saved_in_progress')");
    expect(source).toContain("t('success.finalized')");
    expect(source).toContain("t('success.revised')");
    expect(source).toContain("t('success.notified')");

    // Error messages
    expect(source).toContain("t('errors.select_patient_template')");
    expect(source).toContain("t('errors.no_template_for_services')");
    expect(source).toContain("t('errors.open_or_create_first')");
    expect(source).toContain("t('errors.print_failed')");
    expect(source).toContain("t('errors.notify_failed')");

    // Больше нет хардкоженных русских строк в notify() calls
    expect(source).not.toContain("notify('error', 'Выберите запись и шаблон.')");
    expect(source).not.toContain("notify('success', 'Черновик сохранён.')");
    expect(source).not.toContain("notify('success', 'Отчёт утверждён.')");
    expect(source).not.toContain("notify('success', 'Результаты отправлены пациенту через Telegram.')");
  });

  it('STRAT#19: JSX labels (print feedback, editor header, template resolution) use t()', () => {
    // STRAT#19: JSX strings мигрированы на t()
    const source = fs.readFileSync(workbenchPath, 'utf8');

    // Print feedback
    expect(source).toContain("t('workbench.print_sending')");
    expect(source).toContain("t('workbench.print_sent')");
    expect(source).toContain("t('workbench.print_pdf_failed')");
    expect(source).toContain("t('workbench.print_pdf_invalid')");
    expect(source).toContain("t('workbench.print_pdf_opened')");
    expect(source).toContain("t('workbench.print_pdf_blocked')");

    // Editor header
    expect(source).toContain("t('workbench.title')");
    expect(source).toContain("t('workbench.select_patient_prompt')");
    expect(source).toContain("t('workbench.select_patient_short')");
    expect(source).toContain("t('workbench.patient_label')");
    expect(source).toContain("t('workbench.visit_services')");

    // Template resolution
    expect(source).toContain("t('workbench.resolving_templates')");
    expect(source).toContain("t('workbench.recommended_report')");
    expect(source).toContain("t('workbench.unmapped_services')");
    expect(source).toContain("t('workbench.no_template_found')");
    expect(source).toContain("t('workbench.no_template_hint')");
    expect(source).toContain("t('workbench.show_all_templates')");
    expect(source).toContain("t('workbench.create_report')");
    expect(source).toContain("t('workbench.creating_report')");

    // Больше нет хардкоженных русских строк в print feedback
    expect(source).not.toContain("'Отправляю лабораторный отчёт на печать...'");
    expect(source).not.toContain("'Не удалось сформировать PDF. Проверьте соединение и попробуйте снова.'");
    expect(source).not.toContain("'PDF сформирован некорректно. Обратитесь к администратору.'");
  });
});

describe('LabReportWorkbench draft save integrity (PR3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // custom/no-fake-timers-without-cleanup: fake timers из autosave-теста
  // обязаны возвращаться к real timers в hook, а не только в finally.
  afterEach(() => {
    vi.useRealTimers();
  });

  // vi.mock подменяет методы на vi.fn(), но статический тип остаётся от
  // реального labReportingApi — приводим к vi.fn для setup и инспекции.
  const mockedApi = labReportingApi as unknown as {
    getInstance: ReturnType<typeof vi.fn>;
    updateInstance: ReturnType<typeof vi.fn>;
    bulkSaveValues: ReturnType<typeof vi.fn>;
    finalize: ReturnType<typeof vi.fn>;
    downloadPdf: ReturnType<typeof vi.fn>;
    markPrinted: ReturnType<typeof vi.fn>;
  };
  const mockedPrintService = printService as unknown as {
    printLabResults: ReturnType<typeof vi.fn>;
  };

  const reopenedDraftInstance = {
    id: 77,
    status: 'DRAFT',
    template_id: 3,
    patient_id: 444,
    updated_at: '2026-09-13T08:00:00.123456+00:00',
    signer_snapshot: {},
    available_actions: ['edit', 'save_draft', 'finalize'],
    critical_findings: [],
    sections: [
      {
        key: 'cbc',
        title: 'CBC',
        fields: [
          {
            field_key: 'wbc',
            label: 'Лейкоциты',
            value_type: 'text',
            value_text: '5.2',
            comment: 'утренний забор',
          },
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

  function renderWithActiveInstance(props: Record<string, unknown> = {}) {
    return render(
      <ThemeProvider>
        <LabReportWorkbench
          selectedAppointment={null}
          templates={[]}
          templateResolution={null}
          templateResolutionLoading={false}
          reportHistory={[]}
          recentReports={[]}
          activeInstance={reopenedDraftInstance}
          onInstanceChange={vi.fn()}
          onOpenInstance={vi.fn()}
          onRefreshHistory={vi.fn()}
          onRefreshRecentReports={vi.fn()}
          onQueueChanged={vi.fn()}
          notify={vi.fn()}
          {...props}
        />
      </ThemeProvider>
    );
  }

  it('locks report values and signer inputs while another report is loading', () => {
    renderWithActiveInstance({ instanceTransitionPending: true });

    expect(screen.getByLabelText('Результат: Лейкоциты')).toBeDisabled();
    expect(screen.getByLabelText('ФИО лаборанта')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Сохранить черновик' })).toBeDisabled();
  });

  it('sends the hydrated per-field comment when saving a reopened draft', async () => {
    const onInstanceChange = vi.fn();
    mockedApi.bulkSaveValues.mockResolvedValue({
      instance: { ...reopenedDraftInstance, updated_at: '2026-09-13T08:00:05.000000+00:00' },
    });

    renderWithActiveInstance({ onInstanceChange });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить черновик' }));

    await waitFor(() => expect(mockedApi.bulkSaveValues).toHaveBeenCalled());
    // Дочищаем всю цепочку сохранения, чтобы её «хвост» не выполнялся
    // посреди следующего теста (моки общие на файл).
    await act(async () => {
      for (let i = 0; i < 8; i += 1) {
        await Promise.resolve();
      }
    });

    const payload = mockedApi.bulkSaveValues.mock.calls[0][1] as Array<
      Record<string, unknown>
    >;
    const wbcItem = payload.find((item) => item.field_key === 'wbc');
    expect(wbcItem?.comment).toBe('утренний забор');
    expect(onInstanceChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: 77 }),
      {
        kind: 'update',
        expectedInstanceId: 77,
        operation: { epoch: 0, selectionKey: null, patientId: null },
      },
    );
  });

  it('keeps microsecond version tokens opaque across signer and values saves', async () => {
    const signerResponseUpdated = '2026-09-13T08:00:05.654321+00:00';
    mockedApi.updateInstance.mockResolvedValue({
      ...reopenedDraftInstance,
      updated_at: signerResponseUpdated,
      signer_snapshot: { lab_technician_name: 'Иванов И.И.' },
    });
    mockedApi.bulkSaveValues.mockResolvedValue({
      instance: { ...reopenedDraftInstance, updated_at: '2026-09-13T08:00:06.000000+00:00' },
    });

    renderWithActiveInstance();
    fireEvent.click(screen.getByText('Подписи'));
    fireEvent.change(screen.getByLabelText('ФИО лаборанта'), {
      target: { value: 'Иванов И.И.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить черновик' }));

    await waitFor(() => expect(mockedApi.bulkSaveValues).toHaveBeenCalled());

    // Последовательное сохранение signer -> values: bulk обязан использовать
    // updated_at из ответа первого запроса, иначе получит 409 от себя самого.
    // Ассертим последний вызов: тестовые моки общие на файл, и «хвосты»
    // цепочек предыдущих тестов могут добавлять более ранние вызовы.
    const bulkCalls = mockedApi.bulkSaveValues.mock.calls;
    const ownBulkCall = bulkCalls[bulkCalls.length - 1];
    expect(mockedApi.updateInstance).toHaveBeenCalledWith(
      77,
      { signer_snapshot: expect.objectContaining({ lab_technician_name: 'Иванов И.И.' }) },
      '2026-09-13T08:00:00.123456+00:00'
    );
    expect(ownBulkCall[2]).toBe(signerResponseUpdated);
  });

  it('reuses the committed signer token when bulk save fails and is retried', async () => {
    const signerUpdatedAt = '2026-09-13T08:00:05.654321+00:00';
    const acceptedUpdatedAt = '2026-09-13T08:00:06.654321+00:00';
    const onInstanceChange = vi.fn();
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void> }) => vi.fn(),
    );
    mockedApi.updateInstance.mockReset().mockResolvedValue({
      ...reopenedDraftInstance,
      updated_at: signerUpdatedAt,
      signer_snapshot: { lab_technician_name: 'Иванов И.И.' },
    });
    mockedApi.bulkSaveValues
      .mockReset()
      .mockRejectedValueOnce(new Error('bulk failed'))
      .mockResolvedValueOnce({
        instance: {
          ...reopenedDraftInstance,
          updated_at: acceptedUpdatedAt,
          signer_snapshot: { lab_technician_name: 'Иванов И.И.' },
        },
      });

    renderWithActiveInstance({ onInstanceChange, registerDirtySource });
    fireEvent.change(screen.getByLabelText('Результат: Лейкоциты'), {
      target: { value: '6.8' },
    });
    fireEvent.click(screen.getByText('Подписи'));
    fireEvent.change(screen.getByLabelText('ФИО лаборанта'), {
      target: { value: 'Иванов И.И.' },
    });
    await waitFor(() => expect(registerDirtySource).toHaveBeenCalledTimes(1));
    const source = registerDirtySource.mock.calls[0][0] as { save: () => Promise<void> };

    let firstError: unknown;
    await act(async () => {
      try {
        await source.save();
      } catch (error) {
        firstError = error;
      }
    });
    expect(firstError).toEqual(new Error('bulk failed'));

    await act(async () => {
      await source.save();
    });

    expect(mockedApi.updateInstance).toHaveBeenCalledTimes(1);
    expect(mockedApi.bulkSaveValues).toHaveBeenCalledTimes(2);
    expect(mockedApi.bulkSaveValues.mock.calls[0][2]).toBe(signerUpdatedAt);
    expect(mockedApi.bulkSaveValues.mock.calls[1][2]).toBe(signerUpdatedAt);
    expect(
      (mockedApi.bulkSaveValues.mock.calls[1][1] as Array<Record<string, unknown>>)
        .find((item) => item.field_key === 'wbc')?.value_text,
    ).toBe('6.8');
    expect(onInstanceChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ updated_at: acceptedUpdatedAt }),
      expect.objectContaining({ kind: 'update', expectedInstanceId: 77 }),
    );
  });

  it('clears a partial signer commit after the active instance changes', async () => {
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void> }) => vi.fn(),
    );
    mockedApi.updateInstance.mockReset().mockImplementation(async (id: number) => ({
      ...reopenedDraftInstance,
      id,
      updated_at: `2026-09-13T08:00:0${id === 77 ? '5' : '6'}.000000+00:00`,
      signer_snapshot: { lab_technician_name: 'Иванов И.И.' },
    }));
    mockedApi.bulkSaveValues
      .mockReset()
      .mockRejectedValueOnce(new Error('bulk failed'))
      .mockResolvedValueOnce({
        instance: { ...reopenedDraftInstance, updated_at: '2026-09-13T08:00:07.000000+00:00' },
      });
    const baseProps = {
      selectedAppointment: null,
      templates: [],
      templateResolution: null,
      templateResolutionLoading: false,
      reportHistory: [],
      recentReports: [],
      onInstanceChange: vi.fn(),
      onOpenInstance: vi.fn(),
      onRefreshHistory: vi.fn(),
      onRefreshRecentReports: vi.fn(),
      onQueueChanged: vi.fn(),
      notify: vi.fn(),
      registerDirtySource,
    };
    const utils = render(
      <ThemeProvider>
        <LabReportWorkbench {...baseProps} activeInstance={reopenedDraftInstance} />
      </ThemeProvider>,
    );
    fireEvent.click(screen.getByText('Подписи'));
    fireEvent.change(screen.getByLabelText('ФИО лаборанта'), {
      target: { value: 'Иванов И.И.' },
    });
    await waitFor(() => expect(registerDirtySource).toHaveBeenCalledTimes(1));
    const source = registerDirtySource.mock.calls[0][0] as { save: () => Promise<void> };
    await act(async () => {
      try { await source.save(); } catch { /* expected */ }
    });

    utils.rerender(
      <ThemeProvider>
        <LabReportWorkbench {...baseProps} activeInstance={{ ...reopenedDraftInstance, id: 78 }} />
      </ThemeProvider>,
    );
    utils.rerender(
      <ThemeProvider>
        <LabReportWorkbench {...baseProps} activeInstance={reopenedDraftInstance} />
      </ThemeProvider>,
    );
    fireEvent.click(screen.getByText('Подписи'));
    fireEvent.change(screen.getByLabelText('ФИО лаборанта'), {
      target: { value: 'Иванов И.И.' },
    });
    await act(async () => {
      await source.save();
    });

    expect(mockedApi.updateInstance).toHaveBeenCalledTimes(2);
  });

  it('retries from the bulk token committed before a stale context result', async () => {
    let resolveFirstBulk: ((value: unknown) => void) | null = null;
    const firstBulk = new Promise((resolve) => { resolveFirstBulk = resolve; });
    let operation = { epoch: 1, selectionKey: 'instance:77', patientId: 444 };
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void> }) => vi.fn(),
    );
    mockedApi.updateInstance.mockReset();
    mockedApi.bulkSaveValues
      .mockReset()
      .mockImplementationOnce(() => firstBulk)
      .mockResolvedValueOnce({
        instance: { ...reopenedDraftInstance, updated_at: '2026-09-13T08:00:09.000000+00:00' },
      });
    renderWithActiveInstance({ registerDirtySource, getOperationContext: () => operation });
    fireEvent.change(screen.getByLabelText('Результат: Лейкоциты'), {
      target: { value: '7.2' },
    });
    await waitFor(() => expect(registerDirtySource).toHaveBeenCalledTimes(1));
    const source = registerDirtySource.mock.calls[0][0] as { save: () => Promise<void> };
    let firstError: unknown;
    const firstSave = act(async () => {
      try { await source.save(); } catch (error) { firstError = error; }
    });
    await waitFor(() => expect(mockedApi.bulkSaveValues).toHaveBeenCalledTimes(1));
    operation = { ...operation, epoch: 2 };
    resolveFirstBulk?.({
      instance: { ...reopenedDraftInstance, updated_at: '2026-09-13T08:00:08.000000+00:00' },
    });
    await firstSave;
    expect(firstError).toBeInstanceOf(Error);

    await act(async () => {
      await source.save();
    });
    expect(mockedApi.bulkSaveValues.mock.calls[1][2]).toBe('2026-09-13T08:00:08.000000+00:00');
  });

  it('locks values and signer inputs until an in-flight manual save settles', async () => {
    let resolveBulk: ((value: unknown) => void) | null = null;
    mockedApi.bulkSaveValues.mockReset().mockImplementationOnce(() => new Promise((resolve) => {
      resolveBulk = resolve;
    }));
    renderWithActiveInstance();
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    await waitFor(() => expect(mockedApi.bulkSaveValues).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('Результат: Лейкоциты')).toBeDisabled();
    expect(screen.getByLabelText('ФИО лаборанта')).toBeDisabled();
    resolveBulk?.({ instance: { ...reopenedDraftInstance, updated_at: '2026-09-13T08:00:10.000000+00:00' } });
    await waitFor(() => expect(screen.getByLabelText('Результат: Лейкоциты')).toBeEnabled());
  });

  it('does not open a stale PDF fallback after the report context changes', async () => {
    let resolvePrint: ((value: unknown) => void) | null = null;
    let operation = { epoch: 1, selectionKey: 'instance:77', patientId: 444 };
    mockedPrintService.printLabResults.mockReset().mockImplementationOnce(() => new Promise((resolve) => {
      resolvePrint = resolve;
    }));
    mockedApi.downloadPdf.mockReset();
    mockedApi.markPrinted.mockReset();
    renderWithActiveInstance({
      activeInstance: {
        ...reopenedDraftInstance,
        status: 'FINALIZED',
        available_actions: ['print'],
      },
      getOperationContext: () => operation,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Печать результата' }));
    await waitFor(() => expect(mockedPrintService.printLabResults).toHaveBeenCalledTimes(1));
    operation = { ...operation, epoch: 2 };
    await act(async () => {
      resolvePrint?.({ success: false, error: 'printer offline' });
      await Promise.resolve();
    });

    expect(mockedApi.downloadPdf).not.toHaveBeenCalled();
    expect(mockedApi.markPrinted).not.toHaveBeenCalled();
    expect(screen.queryByText('Отправляю лабораторный отчёт на печать...')).toBeNull();
  });

  it('reports a failed print-status audit even after navigation changed context', async () => {
    let rejectMarkPrinted: ((reason?: unknown) => void) | null = null;
    let operation = { epoch: 1, selectionKey: 'instance:77', patientId: 444 };
    const notify = vi.fn();
    mockedPrintService.printLabResults.mockReset().mockResolvedValueOnce({ success: true });
    mockedApi.markPrinted.mockReset().mockImplementationOnce(() => new Promise((_resolve, reject) => {
      rejectMarkPrinted = reject;
    }));
    renderWithActiveInstance({
      activeInstance: {
        ...reopenedDraftInstance,
        status: 'FINALIZED',
        available_actions: ['print'],
      },
      getOperationContext: () => operation,
      notify,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Печать результата' }));
    await waitFor(() => expect(mockedApi.markPrinted).toHaveBeenCalledWith(77));
    operation = { ...operation, epoch: 2 };
    await act(async () => {
      rejectMarkPrinted?.(new Error('audit unavailable'));
      await Promise.resolve();
    });

    expect(notify).toHaveBeenCalledWith(
      'error',
      expect.stringContaining('статус печати не сохранился'),
    );
  });

  it('does not let the first print timer clear feedback from a second print', async () => {
    vi.useFakeTimers();
    try {
      let resolveSecondPrint: ((value: unknown) => void) | null = null;
      mockedPrintService.printLabResults
        .mockReset()
        .mockResolvedValueOnce({ success: true })
        .mockImplementationOnce(() => new Promise((resolve) => {
          resolveSecondPrint = resolve;
        }));
      mockedApi.markPrinted.mockReset().mockResolvedValue({
        ...reopenedDraftInstance,
        status: 'PRINTED',
        available_actions: ['print'],
      });
      renderWithActiveInstance({
        activeInstance: {
          ...reopenedDraftInstance,
          status: 'FINALIZED',
          available_actions: ['print'],
        },
      });

      fireEvent.click(screen.getByRole('button', { name: 'Печать результата' }));
      await act(async () => {
        for (let i = 0; i < 8; i += 1) await Promise.resolve();
      });
      expect(screen.getByText(/Лабораторный отчёт отправлен на печать/)).toBeInTheDocument();
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });

      fireEvent.click(screen.getByRole('button', { name: 'Печать результата' }));
      expect(screen.getByText('Отправляю лабораторный отчёт на печать...')).toBeInTheDocument();
      await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
      expect(screen.getByText('Отправляю лабораторный отчёт на печать...')).toBeInTheDocument();

      await act(async () => {
        resolveSecondPrint?.({ success: true });
        for (let i = 0; i < 8; i += 1) await Promise.resolve();
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not surface an autosave confirmation for a failed autosave', async () => {
    vi.useFakeTimers();
    try {
      // Все autosave-попытки в этом тесте неудачны: base после неудачи всё
      // равно ставит lastAutoSave, исправленный код — нет.
      mockedApi.bulkSaveValues.mockRejectedValue(
        new Error('Бланк был изменён другим пользователем')
      );

      const utils = renderWithActiveInstance();
      fireEvent.change(screen.getByLabelText('Результат: Лейкоциты'), {
        target: { value: '6.5' },
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });
      expect(mockedApi.bulkSaveValues.mock.calls.length).toBeGreaterThanOrEqual(1);
      // Dirty/retry состояние сохранено: введённое значение не откатилось.
      expect(screen.getByLabelText('Результат: Лейкоциты')).toHaveValue('6.5');

      // Смена активного бланка сбрасывает dirty, но lastAutoSave от
      // НЕУДАЧНОГО autosave не должен «переживать» смену бланка — иначе UI
      // показывает «✓ сохранено» для отчёта, который ни разу не сохранялся.
      const nextInstance = { ...reopenedDraftInstance, id: 78 };
      utils.rerender(
        <ThemeProvider>
          <LabReportWorkbench
            selectedAppointment={null}
            templates={[]}
            templateResolution={null}
            templateResolutionLoading={false}
            reportHistory={[]}
            recentReports={[]}
            activeInstance={nextInstance}
            onInstanceChange={vi.fn()}
            onOpenInstance={vi.fn()}
            onRefreshHistory={vi.fn()}
            onRefreshRecentReports={vi.fn()}
            onQueueChanged={vi.fn()}
            notify={vi.fn()}
          />
        </ThemeProvider>
      );
      await act(async () => {
        await Promise.resolve();
      });

      expect(screen.queryByText((content) => content.includes('✓ сохранено'))).toBeNull();
    } finally {
      vi.useRealTimers();
      vi.clearAllMocks();
    }
  });

  it('does not run a scheduled autosave after the report context changes', async () => {
    vi.useFakeTimers();
    try {
      let operation = { epoch: 1, selectionKey: 'appointment:a-1', patientId: 101 };
      renderWithActiveInstance({ getOperationContext: () => operation });
      fireEvent.change(screen.getByLabelText('Результат: Лейкоциты'), {
        target: { value: '6.6' },
      });
      await act(async () => {
        await Promise.resolve();
      });

      operation = { epoch: 2, selectionKey: 'appointment:a-1', patientId: 101 };
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });

      expect(mockedApi.bulkSaveValues).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
      vi.clearAllMocks();
    }
  });

  it('cancels the autosave timer while the unsaved-transition dialog is open', async () => {
    vi.useFakeTimers();
    try {
      const baseProps = {
        selectedAppointment: null,
        templates: [],
        templateResolution: null,
        templateResolutionLoading: false,
        reportHistory: [],
        recentReports: [],
        activeInstance: reopenedDraftInstance,
        onInstanceChange: vi.fn(),
        onOpenInstance: vi.fn(),
        onRefreshHistory: vi.fn(),
        onRefreshRecentReports: vi.fn(),
        onQueueChanged: vi.fn(),
        notify: vi.fn(),
      };
      const utils = render(
        <ThemeProvider>
          <LabReportWorkbench {...baseProps} pauseAutoSave={false} />
        </ThemeProvider>
      );
      fireEvent.change(screen.getByLabelText('Результат: Лейкоциты'), {
        target: { value: '6.4' },
      });
      await act(async () => {
        await Promise.resolve();
      });

      utils.rerender(
        <ThemeProvider>
          <LabReportWorkbench {...baseProps} pauseAutoSave />
        </ThemeProvider>
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });

      expect(mockedApi.bulkSaveValues).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
      vi.clearAllMocks();
    }
  });

  it('does not finalize the old report when context changes while confirmation is open', async () => {
    let operation = { epoch: 1, selectionKey: 'appointment:a-1', patientId: 101 };
    renderWithActiveInstance({ getOperationContext: () => operation });

    fireEvent.click(screen.getByRole('button', { name: 'Утвердить' }));
    const dialog = await screen.findByRole('dialog');
    operation = { epoch: 2, selectionKey: 'appointment:a-2', patientId: 102 };
    fireEvent.click(within(dialog).getByRole('button', { name: 'Утвердить' }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockedApi.bulkSaveValues).not.toHaveBeenCalled();
    expect(mockedApi.finalize).not.toHaveBeenCalled();
  });

  it('routes superseded-report navigation through the guarded open callback', () => {
    const onOpenInstance = vi.fn();
    const onInstanceChange = vi.fn();

    renderWithActiveInstance({
      activeInstance: { ...reopenedDraftInstance, supersedes_instance_id: 76 },
      onOpenInstance,
      onInstanceChange,
    });

    fireEvent.click(
      screen.getByRole('button', { name: /исправленная версия отчёта #76/i })
    );

    expect(onOpenInstance).toHaveBeenCalledWith(76);
    expect(mockedApi.getInstance).not.toHaveBeenCalled();
    expect(onInstanceChange).not.toHaveBeenCalled();
  });

  it('notifies and rethrows when the registered report save fails', async () => {
    const notify = vi.fn();
    const unregister = vi.fn();
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void> }) => unregister
    );
    mockedApi.bulkSaveValues.mockRejectedValueOnce(new Error('Сохранение отклонено сервером'));

    renderWithActiveInstance({ notify, registerDirtySource });
    fireEvent.change(screen.getByLabelText('Результат: Лейкоциты'), {
      target: { value: '6.7' },
    });

    await waitFor(() => expect(registerDirtySource).toHaveBeenCalledTimes(1));
    const source = registerDirtySource.mock.calls[0][0] as {
      id: string;
      isDirty: () => boolean;
      save: () => Promise<void>;
    };

    expect(source.id).toBe('report');
    expect(source.isDirty()).toBe(true);
    let saveError: unknown;
    await act(async () => {
      try {
        await source.save();
      } catch (error) {
        saveError = error;
      }
    });
    expect(saveError).toEqual(new Error('Сохранение отклонено сервером'));
    expect(notify).toHaveBeenCalledWith('error', 'Сохранение отклонено сервером');
  });
});

describe('LabReportWorkbench add-blank action (PR6)', () => {
  const mockedApi = labReportingApi as unknown as {
    createInstance: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });


  const openInstance = {
    id: 91,
    status: 'DRAFT',
    template_id: 3,
    patient_id: 444,
    visit_id: 728,
    updated_at: '2026-09-13T08:00:00.000000+00:00',
    signer_snapshot: {},
    available_actions: ['edit', 'save_draft', 'finalize'],
    critical_findings: [],
    sections: [
      {
        key: 'cbc',
        title: 'CBC',
        fields: [
          { field_key: 'wbc', label: 'Лейкоциты', value_type: 'text', value_text: '', comment: null },
        ],
      },
    ],
  };
  const resolution = {
    visit_id: 728,
    service_codes: ['CBC'],
    allowed_templates: [
      { id: 3, name: 'CBC template', family: 'hematology' },
      { id: 8, name: 'Urine panel', family: 'urinalysis' },
    ],
    unmapped_service_codes: [],
  };

  function renderAddBlank(props: Record<string, unknown> = {}) {
    return render(
      <ThemeProvider>
        <LabReportWorkbench
          selectedAppointment={{
            id: 17,
            patient_id: 444,
            visit_id: 728,
            patient_fio: 'Test Patient',
            service_codes: ['CBC'],
          }}
          templates={[]}
          templateResolution={resolution}
          templateResolutionLoading={false}
          reportHistory={[]}
          recentReports={[]}
          activeInstance={openInstance}
          onInstanceChange={vi.fn()}
          onOpenInstance={vi.fn()}
          onRefreshHistory={vi.fn(async () => {})}
          onRefreshRecentReports={vi.fn(async () => {})}
          onQueueChanged={vi.fn(async () => {})}
          notify={vi.fn()}
          {...props}
        />
      </ThemeProvider>
    );
  }

  it('renders the add-blank action from server-resolved templates and creates the chosen blank', async () => {
    const onInstanceChange = vi.fn();
    mockedApi.createInstance.mockResolvedValue({
      ...openInstance,
      id: 92,
      template_id: 8,
    });

    renderAddBlank({ onInstanceChange });

    // Только серверно разрешённые шаблоны, оба в списке.
    const select = screen.getByLabelText('Шаблон дополнительного бланка');
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue('3');
    fireEvent.change(select, { target: { value: '8' } });

    fireEvent.click(screen.getByRole('button', { name: /Добавить бланк/ }));

    await waitFor(() => expect(mockedApi.createInstance).toHaveBeenCalled());
    const payload = mockedApi.createInstance.mock.calls[0][0] as Record<string, unknown>;
    expect(payload.template_id).toBe(8);
    expect(payload.patient_id).toBe(444);
    expect(payload.visit_id).toBe(728);
    await waitFor(() => expect(onInstanceChange).toHaveBeenCalled());
    expect((onInstanceChange.mock.calls[0][0] as Record<string, unknown>).id).toBe(92);
    expect(onInstanceChange.mock.calls[0][1]).toEqual({
      kind: 'transition',
      expectedInstanceId: 91,
      operation: { epoch: 0, selectionKey: null, patientId: null },
    });
  });

  it('stops refreshes and success feedback when the parent rejects a late create result', async () => {
    const onInstanceChange = vi.fn(() => false);
    const onRefreshHistory = vi.fn(async () => {});
    const onRefreshRecentReports = vi.fn(async () => {});
    const onQueueChanged = vi.fn(async () => {});
    const notify = vi.fn();
    mockedApi.createInstance.mockResolvedValue({
      ...openInstance,
      id: 93,
      template_id: 8,
    });

    renderAddBlank({
      onInstanceChange,
      onRefreshHistory,
      onRefreshRecentReports,
      onQueueChanged,
      notify,
    });
    fireEvent.change(screen.getByLabelText('Шаблон дополнительного бланка'), {
      target: { value: '8' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Добавить бланк/ }));

    await waitFor(() => expect(onInstanceChange).toHaveBeenCalledTimes(1));
    expect(onRefreshHistory).not.toHaveBeenCalled();
    expect(onRefreshRecentReports).not.toHaveBeenCalled();
    expect(onQueueChanged).not.toHaveBeenCalled();
    expect(notify).not.toHaveBeenCalledWith('success', expect.any(String));
  });

  it('disables the add-blank action while the open draft is dirty', async () => {
    renderAddBlank();
    fireEvent.change(screen.getByLabelText('Результат: Лейкоциты'), {
      target: { value: '7' },
    });
    const button = screen.getByRole('button', { name: /Добавить бланк/ });
    expect(button).toBeDisabled();
    // Создание не выполняется.
    expect(mockedApi.createInstance).not.toHaveBeenCalled();
  });

  it('renders no add-blank action without server-resolved templates', () => {
    renderAddBlank({ templateResolution: null });
    expect(screen.queryByLabelText('Шаблон дополнительного бланка')).toBeNull();
    expect(screen.queryByRole('button', { name: /Добавить бланк/ })).toBeNull();
  });
});
