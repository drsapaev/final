// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React from 'react';
import '@testing-library/jest-dom';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LabReportWorkbench from '../LabReportWorkbench';
import { labReportingApi } from '../../../api/labReporting';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import { MacOSThemeProvider } from '../../../theme/macosTheme';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workbenchPath = path.resolve(__dirname, '../LabReportWorkbench.tsx');

vi.mock('../../../api/labReporting', () => ({
  labReportingApi: {
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
      <MacOSThemeProvider>
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
      </MacOSThemeProvider>
    );

    expect(
      screen.getByText((content) =>
        content.includes('Выберите пациента из очереди или откройте уже существующий лабораторный отчёт')
      )
    ).toBeInTheDocument();
    expect(screen.getByText('Недавние лабораторные отчёты')).toBeInTheDocument();
    expect(screen.getByText(/Тестовый Пациент Регистратура/i)).toBeInTheDocument();

    const reportButton = screen.getByText('ОАК').closest('button');
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
      <MacOSThemeProvider>
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
      </MacOSThemeProvider>
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
      <MacOSThemeProvider>
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
      </MacOSThemeProvider>
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
