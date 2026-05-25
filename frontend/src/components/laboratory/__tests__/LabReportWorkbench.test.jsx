import React from 'react';
import '@testing-library/jest-dom';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LabReportWorkbench from '../LabReportWorkbench';
import { labReportingApi } from '../../../api/labReporting';
import { ThemeProvider } from '../../../contexts/ThemeContext.jsx';
import { MacOSThemeProvider } from '../../../theme/macosTheme.jsx';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workbenchPath = path.resolve(__dirname, '../LabReportWorkbench.jsx');

vi.mock('../../../api/labReporting', () => ({
  labReportingApi: {
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    markReady: vi.fn(),
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
      screen.getByText('Выберите пациента из очереди или откройте уже существующий лабораторный бланк из списка ниже.')
    ).toBeInTheDocument();
    expect(screen.getByText('Недавние лабораторные бланки')).toBeInTheDocument();
    expect(screen.getByText(/Тестовый Пациент Регистратура/i)).toBeInTheDocument();

    const reportButton = screen.getByText('ОАК').closest('button');
    expect(reportButton).not.toBeNull();
    fireEvent.click(reportButton);

    expect(onOpenInstance).toHaveBeenCalledWith(22);
  });

  it('uses backend-provided action availability instead of local finalized status rules', () => {
    const source = fs.readFileSync(workbenchPath, 'utf8');

    expect(source).toContain('function hasLabReportAction(instance, action)');
    expect(source).toContain("const canEditActiveInstance = hasLabReportAction(activeInstance, 'edit')");
    expect(source).toContain("const canFinalize = hasLabReportAction(activeInstance, 'finalize')");
    expect(source).toContain("const canRevise = hasLabReportAction(activeInstance, 'revise')");
    expect(source).not.toContain("activeInstance.status !== 'FINALIZED' && activeInstance.status !== 'PRINTED'");
    expect(source).not.toContain("activeInstance.status === 'FINALIZED' || activeInstance.status === 'PRINTED'");
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
      content.includes('Единственный допустимый бланк найден')
    );
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(labReportingApi.createInstance).not.toHaveBeenCalled();
    expect(onOpenInstance).not.toHaveBeenCalled();
    expect(notify).not.toHaveBeenCalledWith(
      'success',
      expect.stringContaining('автоматически')
    );
  });
});
