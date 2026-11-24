import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';
import type { WorkspaceLabReport, WorkspaceLabs } from '@/api/emrWorkspace';

/**
 * EMRLAB-FE-001..004 (audit 3886, round 15) — fail-first.
 *
 * 001: секция слала несуществующий singular `visit_id` (сервер принимает
 *      visit_ids-массив) — Doctor получал ВСЕ свои визиты: чужие пациенты
 *      под заголовком активного пациента.
 * 002: без epoch/abort поздний ответ/ошибка пациента A перезаписывал
 *      список/spinner пациента B; пустой контекст не чистил строки.
 * 003: limit=20 без серверного статус-фильтра: 20 более новых черновиков
 *      вытесняли старые finalized за пределы выборки, клиентский фильтр
 *      показывал «нет результатов».
 * 004: signed/read-only EMR гллушил pointer-events всей секции и прятал
 *      PDF-кнопку, хотя канонический PDF разрешён Doctor'у на чтение.
 * Тесты ниже падают на до-фиксном коде.
 */

const listInstancesMock = vi.hoisted(() => vi.fn());
const getWorkspaceLabsMock = vi.hoisted(() => vi.fn());
const reviewLabVersionMock = vi.hoisted(() => vi.fn());

vi.mock('@/api/emrWorkspace', () => ({
  getWorkspaceLabs: getWorkspaceLabsMock,
  reviewLabVersion: reviewLabVersionMock,
}));

vi.mock('../../../../hooks/useLabReporting', () => ({
  useLabReporting: () => ({
    listInstances: listInstancesMock,
    createOrder: vi.fn(),
    downloadPdf: vi.fn(),
    listTemplates: vi.fn().mockResolvedValue([]),
    getInstance: vi.fn(),
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    finalize: vi.fn(),
    revise: vi.fn(),
    markPrinted: vi.fn(),
    previewInstancePdf: vi.fn(),
  }),
}));

import LabResultsSectionRaw from '../LabResultsSection';

const LabResultsSection = LabResultsSectionRaw as unknown as React.ComponentType<Record<string, unknown>>;

function finalized(id: number, name: string, daysAgo = 0): Record<string, unknown> {
  return {
    id,
    template_name: name,
    status: 'FINALIZED',
    finalized_at: new Date(Date.now() - daysAgo * 86400000).toISOString(),
    flagged_findings_count: 0,
  };
}

function draft(id: number, name: string): Record<string, unknown> {
  return { id, template_name: name, status: 'IN_PROGRESS', updated_at: new Date().toISOString() };
}

const noWorkspaceLabs: WorkspaceLabs = { orders: [], unlinked_reports: [], executions: [], invoices: [] };

function workspaceLabs(reports: WorkspaceLabReport[]): WorkspaceLabs {
  return {
    ...noWorkspaceLabs,
    orders: [{ id: 77, status: 'completed', created_at: '2026-07-01T09:00:00Z', reports }],
  };
}

function report(id: number, name: string, supersedes: number | null = null): WorkspaceLabReport {
  return {
    id, template_name: name, status: 'FINALIZED', finalized_at: '2026-07-01T11:00:00Z',
    supersedes_instance_id: supersedes, is_current_final: true, reviews: [],
  };
}

beforeEach(async () => {
  vi.clearAllMocks();
  getWorkspaceLabsMock.mockReset().mockResolvedValue(noWorkspaceLabs);
  await act(async () => { await i18n.changeLanguage('ru'); });
});

describe('EMRLAB-FE-001: canonical list parameters', () => {
  it('sends visit_ids as an ARRAY plus patient_id (no singular visit_id)', async () => {
    listInstancesMock.mockResolvedValue([]);
    render(
      <ThemeProvider>
        <LabResultsSection patientId={2} visitId={10} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(listInstancesMock).toHaveBeenCalled());
    for (const call of listInstancesMock.mock.calls) {
      const params = call[0] as Record<string, unknown>;
      expect(params.visit_id).toBeUndefined();
      expect(params.visit_ids).toEqual([10]);
      expect(params.patient_id).toBe(2);
      expect(['FINALIZED', 'PRINTED']).toContain(params.status);
    }
    expect(listInstancesMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

describe('EMRLAB-FE-002: response ownership across context switches', () => {
  it('a late patient-A response cannot overwrite patient B\'s list', async () => {
    let resolveA: ((value: unknown[]) => void) | null = null;
    // Диспетчер по visit: до-фиксный код слал visit_id (singular),
    // фиксированный — visit_ids-массив; оба должны попадать в A-ветку.
    listInstancesMock.mockImplementation((params: Record<string, unknown>) => {
      const isA = params.visit_id === 5 || (Array.isArray(params.visit_ids) && params.visit_ids.includes(5));
      if (isA) {
        return new Promise((resolve) => { resolveA = resolve; });
      }
      return Promise.resolve([finalized(22, 'Отчёт B', 1)]);
    });
    const view = render(
      <ThemeProvider>
        <LabResultsSection patientId={1} visitId={5} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(listInstancesMock).toHaveBeenCalled());
    view.rerender(
      <ThemeProvider>
        <LabResultsSection patientId={2} visitId={6} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Отчёт B')).toBeInTheDocument());

    // Поздний ответ пациента A прибывает ПОСЛЕ успеха B.
    await act(async () => {
      resolveA?.([finalized(11, 'Отчёт A', 10)]);
      for (let i = 0; i < 8; i += 1) await Promise.resolve();
    });

    // Список остаётся списком пациента B.
    expect(screen.getByText('Отчёт B')).toBeInTheDocument();
    expect(screen.queryByText('Отчёт A')).toBeNull();
  });

  it('a late patient-A FAILURE cannot hide patient B\'s results or spinner', async () => {
    let rejectA: ((reason?: unknown) => void) | null = null;
    // Диспетчер по visit (см. предыдущий тест): A — отложенный reject.
    listInstancesMock.mockImplementation((params: Record<string, unknown>) => {
      const isA = params.visit_id === 5 || (Array.isArray(params.visit_ids) && params.visit_ids.includes(5));
      if (isA) {
        return new Promise((_resolve, reject) => { rejectA = reject; });
      }
      return Promise.resolve([finalized(23, 'Отчёт B2', 1)]);
    });
    const view = render(
      <ThemeProvider>
        <LabResultsSection patientId={1} visitId={5} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(listInstancesMock).toHaveBeenCalled());
    view.rerender(
      <ThemeProvider>
        <LabResultsSection patientId={2} visitId={6} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Отчёт B2')).toBeInTheDocument());

    await act(async () => {
      rejectA?.(new Error('late A failure'));
      for (let i = 0; i < 8; i += 1) await Promise.resolve();
    });
    expect(screen.getByText('Отчёт B2')).toBeInTheDocument();
    expect(screen.queryByText('Не удалось загрузить результаты анализов.')).toBeNull();
  });

  it('clearing the context (null/null) immediately empties a populated list', async () => {
    listInstancesMock.mockResolvedValue([finalized(30, 'Отчёт C', 1)]);
    const view = render(
      <ThemeProvider>
        <LabResultsSection patientId={3} visitId={7} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Отчёт C')).toBeInTheDocument());
    view.rerender(
      <ThemeProvider>
        <LabResultsSection patientId={null} visitId={null} />
      </ThemeProvider>,
    );
    await act(async () => {
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });
    expect(screen.queryByText('Отчёт C')).toBeNull();
  });
});

describe('EMRLAB-FE-003: server-side status filtering before the limit', () => {
  it('an older finalized report is NOT hidden by 20 newer drafts', async () => {
    // Как реальный сервер: без статус-параметра возвращает последние N
    // записей (20 новых черновиков — finalized туда не попал); с
    // status=FINALIZED возвращает сам финализированный отчёт.
    const draftsPage = Array.from({ length: 20 }, (_v, i) => draft(100 + i, `Черновик ${i}`));
    listInstancesMock.mockImplementation((params: Record<string, unknown>) => {
      if (params.status === 'FINALIZED') {
        return Promise.resolve([finalized(33, 'Старый финализированный', 30)]);
      }
      if (params.status === 'PRINTED') {
        return Promise.resolve([]);
      }
      // Эмулируем до-фиксный запрос (без status): последние 20 — все drafts.
      return Promise.resolve(draftsPage);
    });
    render(
      <ThemeProvider>
        <LabResultsSection patientId={4} visitId={8} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Старый финализированный')).toBeInTheDocument(), { timeout: 3000 });
    // До фикса: 20 drafts приходили без статус-фильтра, клиентский
    // filter() вырезал их все → «нет результатов».
    expect(screen.queryByText(/Нет результатов/i)).toBeNull();
    for (const call of listInstancesMock.mock.calls) {
      expect((call[0] as Record<string, unknown>).status).toBeDefined();
    }
  });
});

describe('EMRLAB-FE-004: read-only does not revoke read access', () => {
  it('a signed/read-only section still shows the PDF action and expands', async () => {
    listInstancesMock.mockResolvedValue([finalized(44, 'Гемоглобин', 2)]);
    render(
      <ThemeProvider>
        <LabResultsSection patientId={5} visitId={9} disabled />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Гемоглобин')).toBeInTheDocument(), { timeout: 3000 });
    // EMRCOLLAPSE-FE-001 (audit 3886, round 21): a collapsed section body is
    // now inert/aria-hidden, so content actions are only in the a11y tree once
    // the section is expanded. The pre-round-21 assertions passed through the
    // a11y leak (querying actions inside a visually collapsed body); expanding
    // first matches what this test has always claimed ("…and expands").
    fireEvent.click(screen.getByRole('button', { name: /Результаты анализов/ }));
    expect(screen.getByRole('button', { name: /Результаты анализов/ })).toHaveAttribute('aria-expanded', 'true');
    // PDF-кнопка доступна в read-only (мутации — нет):
    expect(screen.getByRole('button', { name: /Скачать PDF: Гемоглобин/ })).toBeVisible();
    expect(screen.queryByRole('button', { name: /Заказать анализы/ })).toBeNull();
  });

  it('an interactive section keeps the order action (mutation gate unchanged)', async () => {
    listInstancesMock.mockResolvedValue([finalized(45, 'Лейкоциты', 2)]);
    render(
      <ThemeProvider>
        <LabResultsSection patientId={5} visitId={9} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByRole('button', { name: /Заказать анализы/ })).toBeVisible(), { timeout: 3000 });
    // EMRCOLLAPSE-FE-001 (round 21): expand before querying body content.
    fireEvent.click(screen.getByRole('button', { name: /Результаты анализов/ }));
    expect(screen.getByRole('button', { name: /Скачать PDF: Лейкоциты/ })).toBeVisible();
  });
});

describe('Lab results refresh within the same encounter', () => {
  it('retries the failed list and opens the newly finalized correction by exact version', async () => {
    listInstancesMock.mockRejectedValue(new Error('Synthetic results outage'));
    render(<ThemeProvider><LabResultsSection patientId={1} visitId={5} reviewerId={19} /></ThemeProvider>);

    expect(await screen.findByRole('alert')).toHaveTextContent(i18n.t('emr_workspace.load_error'));
    listInstancesMock.mockResolvedValue([]);
    fireEvent.click(screen.getByRole('button', { name: i18n.t('emr_workspace.retry') }));
    fireEvent.click(screen.getByRole('button', { name: /Результаты анализов/ }));
    expect(await screen.findByText(i18n.t('empty.no_lab_results'))).toBeVisible();

    const original = report(11, 'SYNTHETIC original');
    getWorkspaceLabsMock.mockResolvedValue(workspaceLabs([original]));
    listInstancesMock.mockResolvedValue([finalized(11, original.template_name)]);
    fireEvent.click(screen.getByRole('button', { name: i18n.t('emr_workspace.lab_refresh') }));
    expect(await screen.findByText(original.template_name)).toBeVisible();
    expect(screen.getByRole('button', { name: i18n.t('emr_workspace.lab_review') })).toBeEnabled();

    const correction = report(12, 'SYNTHETIC correction', original.id);
    getWorkspaceLabsMock.mockResolvedValue(workspaceLabs([{ ...original, is_current_final: false }, correction]));
    listInstancesMock.mockResolvedValue([
      finalized(11, original.template_name), { ...finalized(12, correction.template_name), flagged_findings_count: 2 },
    ]);
    fireEvent.click(screen.getByRole('button', { name: i18n.t('emr_workspace.lab_refresh') }));
    expect(screen.queryByRole('button', { name: i18n.t('emr_workspace.lab_review') })).toBeNull();

    expect(await screen.findByText(correction.template_name)).toBeVisible();
    expect(screen.getByText(i18n.t('emr_workspace.lab_previous_version'))).toBeVisible();
    expect(screen.getByRole('button', { name: `Скачать PDF: ${correction.template_name}` })).toBeVisible();
    expect(screen.getByText(/2 отклонений/)).toBeVisible();
    const latestReview = screen.getByRole('button', { name: i18n.t('emr_workspace.lab_review') });
    fireEvent.click(latestReview);
    await waitFor(() => expect(reviewLabVersionMock).toHaveBeenCalledExactlyOnceWith(5, 1, correction.id, ''));
    expect(getWorkspaceLabsMock).toHaveBeenLastCalledWith(5, 1, expect.any(AbortSignal));
  });

  it('discards both late refresh responses after changing patients', async () => {
    listInstancesMock.mockResolvedValue([]);
    const view = render(<ThemeProvider><LabResultsSection patientId={1} visitId={5} /></ThemeProvider>);
    const refresh = await screen.findByRole('button', { name: i18n.t('emr_workspace.lab_refresh') });
    await waitFor(() => expect(refresh).toBeEnabled());

    let resolveOldResults!: (value: Record<string, unknown>[]) => void;
    let resolveOldWorkspace!: (value: WorkspaceLabs) => void;
    listInstancesMock.mockImplementationOnce(() => new Promise(resolve => { resolveOldResults = resolve; }));
    getWorkspaceLabsMock.mockImplementationOnce(() => new Promise(resolve => { resolveOldWorkspace = resolve; }));
    fireEvent.click(refresh);
    await waitFor(() => expect(resolveOldResults).toBeTypeOf('function'));

    const current = report(22, 'SYNTHETIC current patient');
    getWorkspaceLabsMock.mockResolvedValue(workspaceLabs([current]));
    listInstancesMock.mockResolvedValue([
      { ...finalized(22, current.template_name), visit_id: 6, patient_id: 2 },
      { ...finalized(23, 'SYNTHETIC unexpected scope'), visit_id: 5, patient_id: 1 },
    ]);
    view.rerender(<ThemeProvider><LabResultsSection patientId={2} visitId={6} /></ThemeProvider>);
    expect(await screen.findByText(current.template_name)).toBeInTheDocument();

    const previous = report(11, 'SYNTHETIC previous patient');
    await act(async () => {
      resolveOldResults([finalized(11, previous.template_name)]);
      resolveOldWorkspace(workspaceLabs([previous]));
    });
    expect(screen.getByText(current.template_name)).toBeInTheDocument();
    expect(screen.queryByText(previous.template_name)).toBeNull();
    expect(screen.queryByText('SYNTHETIC unexpected scope')).toBeNull();
  });
});
