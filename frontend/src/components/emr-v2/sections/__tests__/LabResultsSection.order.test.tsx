import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * EMRORDER-FE-001 (audit 3886, round 19) — fail-first.
 *
 * The old handleOrder sent the closure-captured patientId/visitId to
 * POST /lab/orders as soon as the confirm dialog resolved — without checking
 * that the mounted EMR still belonged to that context. A doctor owning both
 * visits switching from patient A to patient B while A's confirmation was
 * pending created A's order and showed a success toast inside B's active
 * EMR. The template list opened under A stayed attached to the component
 * across the switch as well.
 * The tests below fail on the pre-fix source.
 */

const listInstancesMock = vi.hoisted(() => vi.fn());
const createOrderMock = vi.hoisted(() => vi.fn());
const listTemplatesMock = vi.hoisted(() => vi.fn());
const confirmMock = vi.hoisted(() => vi.fn());
const successMock = vi.hoisted(() => vi.fn());
const errorMock = vi.hoisted(() => vi.fn());

vi.mock('../../../../hooks/useLabReporting', () => ({
  useLabReporting: () => ({
    listInstances: listInstancesMock,
    createOrder: createOrderMock,
    downloadPdf: vi.fn(),
    listTemplates: listTemplatesMock,
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

vi.mock('../../../common/ConfirmDialog', () => ({
  useConfirm: () => [confirmMock, null],
}));

vi.mock('@/services/notify', () => ({
  default: { success: successMock, error: errorMock, warning: vi.fn(), info: vi.fn() },
}));

import LabResultsSectionRaw from '../LabResultsSection';

const LabResultsSection = LabResultsSectionRaw as unknown as React.ComponentType<Record<string, unknown>>;

const publishedTemplate = {
  id: 77,
  name: 'Общий анализ крови',
  code: 'CBC',
  family: 'Гематология',
  published_version_id: 901,
};

async function flush(times = 8) {
  for (let i = 0; i < times; i += 1) await Promise.resolve();
}

beforeEach(async () => {
  vi.clearAllMocks();
  listInstancesMock.mockResolvedValue([]);
  await act(async () => { await i18n.changeLanguage('ru'); });
});

async function openOrderModal() {
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Заказать анализы/ })); });
  await waitFor(() => expect(listTemplatesMock).toHaveBeenCalled());
  await act(async () => { await flush(); });
}

describe('EMRORDER-FE-001: order intent is bound to its patient/visit context', () => {
  it('a confirm resolved after the switch to patient B creates NO order and NO success toast', async () => {
    listTemplatesMock.mockResolvedValue([publishedTemplate]);
    let resolveConfirm: ((v: boolean) => void) | null = null;
    confirmMock.mockImplementation(() => new Promise<boolean>((resolve) => { resolveConfirm = resolve; }));

    const view = render(
      <ThemeProvider>
        <LabResultsSection patientId={1} visitId={5} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByRole('button', { name: /Заказать анализы/ })).toBeInTheDocument());

    // Doctor starts ordering template T under patient A / visit 5.
    await openOrderModal();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Общий анализ крови/ })); });

    // The parent re-renders the SAME mounted section for patient B / visit 6
    // while A's confirmation is pending.
    view.rerender(
      <ThemeProvider>
        <LabResultsSection patientId={2} visitId={6} />
      </ThemeProvider>,
    );

    // A's late confirm resolves TRUE.
    await act(async () => { resolveConfirm?.(true); await flush(); });

    // No stale A order, no success toast attributed to B's EMR.
    expect(createOrderMock).not.toHaveBeenCalled();
    expect(successMock).not.toHaveBeenCalled();
    // The order modal was invalidated by the context switch.
    expect(screen.queryByText('Гематология')).toBeNull();
    expect(screen.queryByRole('button', { name: /Общий анализ крови/ })).toBeNull();
  });

  it('control: an unchanged context still creates exactly one order with the right ids', async () => {
    listTemplatesMock.mockResolvedValue([publishedTemplate]);
    confirmMock.mockResolvedValue(true);
    createOrderMock.mockResolvedValue({ id: 123 });

    render(
      <ThemeProvider>
        <LabResultsSection patientId={1} visitId={5} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByRole('button', { name: /Заказать анализы/ })).toBeInTheDocument());
    await openOrderModal();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Общий анализ крови/ })); });
    await act(async () => { await flush(); });

    expect(createOrderMock).toHaveBeenCalledTimes(1);
    expect(createOrderMock).toHaveBeenCalledWith({
      template_id: 77,
      patient_id: 1,
      visit_id: 5,
    });
    expect(successMock).toHaveBeenCalledTimes(1);
    // Modal closed after success.
    expect(screen.queryByText('Гематология')).toBeNull();
  });

  it('a template list started under A does not render after the switch to B', async () => {
    let resolveTemplates: ((v: unknown) => void) | null = null;
    listTemplatesMock.mockImplementation(() => new Promise((resolve) => { resolveTemplates = resolve; }));

    const view = render(
      <ThemeProvider>
        <LabResultsSection patientId={1} visitId={5} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByRole('button', { name: /Заказать анализы/ })).toBeInTheDocument());
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Заказать анализы/ })); });
    await waitFor(() => expect(listTemplatesMock).toHaveBeenCalled());

    // Switch to B while A's template fetch is in flight.
    view.rerender(
      <ThemeProvider>
        <LabResultsSection patientId={2} visitId={6} />
      </ThemeProvider>,
    );

    // A's template list resolves late.
    await act(async () => { resolveTemplates?.([publishedTemplate]); await flush(); });
    expect(screen.queryByText('Гематология')).toBeNull();
    expect(screen.queryByRole('button', { name: /Общий анализ крови/ })).toBeNull();
  });

  it('backend rejection surfaces an error, never a success', async () => {
    listTemplatesMock.mockResolvedValue([publishedTemplate]);
    confirmMock.mockResolvedValue(true);
    createOrderMock.mockRejectedValue(new Error('boom'));

    render(
      <ThemeProvider>
        <LabResultsSection patientId={1} visitId={5} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByRole('button', { name: /Заказать анализы/ })).toBeInTheDocument());
    await openOrderModal();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Общий анализ крови/ })); });
    await act(async () => { await flush(); });

    expect(errorMock).toHaveBeenCalled();
    expect(successMock).not.toHaveBeenCalled();
  });
});
