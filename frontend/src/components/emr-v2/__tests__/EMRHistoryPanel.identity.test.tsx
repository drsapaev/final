import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * EMRHIST-FE-001/002 (audit 3886, round 19) — fail-first.
 *
 * 001: the panel read `edited_at`/`edited_by`, but the backend history
 *      contract (EMRRevisionSummary) publishes `created_at`/`created_by` —
 *      every revision rendered a blank date («—») and no author.
 * 002: history responses were not bound to the visit: a late response (or
 *      late failure) of visit A overwrote/hidden visit B's rows while the
 *      panel showed B.
 * The tests below fail on the pre-fix source.
 */

const getMock = vi.hoisted(() => vi.fn());

vi.mock('../../../api/client', () => ({
  apiClient: { get: getMock },
  setSessionInvalidationListener: vi.fn(),
}));

import EMRHistoryPanelRaw from '../EMRHistoryPanel';

const EMRHistoryPanel = EMRHistoryPanelRaw as unknown as React.ComponentType<Record<string, unknown>>;

const revisionA = (n: number) => ({
  id: 100 + n,
  version: n,
  change_type: 'updated',
  change_summary: `ревизия A${n}`,
  created_at: '2026-11-01T10:00:00Z',
  created_by: 11,
});
const revisionB = (n: number) => ({
  id: 200 + n,
  version: n,
  change_type: 'signed',
  change_summary: `ревизия B${n}`,
  created_at: '2026-11-06T06:00:00Z',
  created_by: 17,
});

async function flush(times = 8) {
  for (let i = 0; i < times; i += 1) await Promise.resolve();
}

beforeEach(async () => {
  vi.clearAllMocks();
  await act(async () => { await i18n.changeLanguage('ru'); });
});

describe('EMRHIST-FE-001: canonical DTO keys created_at/created_by', () => {
  it('renders the formatted date and the author id from the backend contract', async () => {
    getMock.mockResolvedValue({
      data: {
        revisions: [{
          id: 9,
          version: 2,
          change_type: 'updated',
          created_at: '2026-11-06T06:00:00Z',
          created_by: 17,
        }],
      },
    });
    render(
      <ThemeProvider>
        <EMRHistoryPanel visitId={5} isOpen />
      </ThemeProvider>,
    );
    await waitFor(() => expect(getMock).toHaveBeenCalledWith('/v2/emr/5/history'));

    // Pre-fix: formatDate(revision.edited_at) rendered «—» and no author.
    // Flake stabilization (3 CI strikes on 2026-11-10: main ef13052eb,
    // #3971 head d87ad687, main 4f42f84f — all passed on re-run with
    // identical trees): the waitFor above only confirms the FETCH CALL,
    // not that the mocked response has resolved and React has committed
    // the rows to the DOM. A synchronous getByText races that commit.
    // findByText waits for the first date render.
    const dateText = (await screen.findByText(/2026/)).textContent ?? '';
    expect(dateText).not.toBe('—');
    expect(dateText).toMatch(/\d{2}\.\d{2}\.\d{4}/);
    expect(screen.getByText(/#17/)).toBeInTheDocument();
  });

  it('a revision without an optional change_summary is still rendered', async () => {
    getMock.mockResolvedValue({
      data: {
        revisions: [{
          id: 10,
          version: 3,
          change_type: 'amended',
          created_at: '2026-11-06T07:30:00Z',
          created_by: 4,
        }],
      },
    });
    render(
      <ThemeProvider>
        <EMRHistoryPanel visitId={5} isOpen />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText(/#4/)).toBeInTheDocument());
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });
});

describe('EMRHIST-FE-002: history responses are bound to the visit', () => {
  it('a late visit-A response cannot overwrite visit B\'s rows', async () => {
    let resolveA: ((v: unknown) => void) | null = null;
    getMock.mockImplementation((url: string) => {
      if (url.includes('/5/history')) {
        return new Promise((resolve) => { resolveA = resolve; });
      }
      return Promise.resolve({ data: { revisions: [revisionB(2)] } });
    });

    const view = render(
      <ThemeProvider>
        <EMRHistoryPanel visitId={5} isOpen />
      </ThemeProvider>,
    );
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    view.rerender(
      <ThemeProvider>
        <EMRHistoryPanel visitId={6} isOpen />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('ревизия B2')).toBeInTheDocument());

    // A's late response arrives AFTER B is visible.
    await act(async () => { resolveA?.({ data: { revisions: [revisionA(1)] } }); await flush(); });

    // B's audit trail stays; A's rows never appear.
    expect(screen.getByText('ревизия B2')).toBeInTheDocument();
    expect(screen.queryByText('ревизия A1')).toBeNull();
  });

  it('a late visit-A FAILURE cannot hide visit B\'s rows', async () => {
    let rejectA: ((reason?: unknown) => void) | null = null;
    getMock.mockImplementation((url: string) => {
      if (url.includes('/5/history')) {
        return new Promise((_resolve, reject) => { rejectA = reject; });
      }
      return Promise.resolve({ data: { revisions: [revisionB(3)] } });
    });

    const view = render(
      <ThemeProvider>
        <EMRHistoryPanel visitId={5} isOpen />
      </ThemeProvider>,
    );
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    view.rerender(
      <ThemeProvider>
        <EMRHistoryPanel visitId={6} isOpen />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('ревизия B3')).toBeInTheDocument());

    await act(async () => { rejectA?.(new Error('late A failure')); await flush(); });
    expect(screen.getByText('ревизия B3')).toBeInTheDocument();
    expect(screen.queryByText(/Не удалось загрузить историю/)).toBeNull();
  });

  it('a visit switch immediately clears the previous visit\'s rows while the new request is pending', async () => {
    let resolveB: ((v: unknown) => void) | null = null;
    getMock.mockImplementation((url: string) => {
      if (url.includes('/5/history')) {
        return Promise.resolve({ data: { revisions: [revisionA(1)] } });
      }
      return new Promise((resolve) => { resolveB = resolve; });
    });

    const view = render(
      <ThemeProvider>
        <EMRHistoryPanel visitId={5} isOpen />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('ревизия A1')).toBeInTheDocument());

    // Switch to B: A's rows must disappear IMMEDIATELY (before B resolves).
    view.rerender(
      <ThemeProvider>
        <EMRHistoryPanel visitId={6} isOpen />
      </ThemeProvider>,
    );
    expect(screen.queryByText('ревизия A1')).toBeNull();
    expect(screen.getByText(/Загрузка/)).toBeInTheDocument();

    await act(async () => { resolveB?.({ data: { revisions: [revisionB(2)] } }); await flush(); });
    expect(screen.getByText('ревизия B2')).toBeInTheDocument();
  });
});
