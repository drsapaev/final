import React from 'react';
import '@testing-library/jest-dom';
import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * EMRHIST-FE-002 diff side (audit 3886, round 19) — fail-first.
 *
 * The old EMRDiffViewer kept the previous diff rendered until a NEW request
 * SUCCEEDED, and bound nothing to the visit: a pending request left the
 * previous visit's field differences visible under the new context, and a
 * late response of the old request overwrote the new one's result.
 * The tests below fail on the pre-fix source.
 */

const getMock = vi.hoisted(() => vi.fn());

vi.mock('../../../api/client', () => ({
  apiClient: { get: getMock },
  setSessionInvalidationListener: vi.fn(),
}));

import EMRDiffViewerRaw from '../EMRDiffViewer';

const EMRDiffViewer = EMRDiffViewerRaw as unknown as React.ComponentType<Record<string, unknown>>;

const diffA = {
  summary: 'Сводка различий A',
  changes: [{ field: 'complaints', change_type: 'modified', old_value: 'a', new_value: 'b' }],
};
const diffB = {
  summary: 'Сводка различий B',
  changes: [{ field: 'diagnosis', change_type: 'modified', old_value: 'x', new_value: 'y' }],
};

async function flush(times = 8) {
  for (let i = 0; i < times; i += 1) await Promise.resolve();
}

beforeEach(async () => {
  vi.clearAllMocks();
  await act(async () => { await i18n.changeLanguage('ru'); });
});

describe('EMRHIST-FE-002 (diff): responses are bound to the request identity', () => {
  it('a late visit-A diff cannot overwrite visit B\'s diff', async () => {
    let resolveA: ((v: unknown) => void) | null = null;
    getMock.mockImplementation((url: string) => {
      if (url.includes('/5/diff')) {
        return new Promise((resolve) => { resolveA = resolve; });
      }
      return Promise.resolve({ data: diffB });
    });

    const view = render(
      <ThemeProvider>
        <EMRDiffViewer visitId={5} versionFrom={1} versionTo={2} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    view.rerender(
      <ThemeProvider>
        <EMRDiffViewer visitId={6} versionFrom={1} versionTo={2} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Сводка различий B')).toBeInTheDocument());

    await act(async () => { resolveA?.({ data: diffA }); await flush(); });

    expect(screen.getByText('Сводка различий B')).toBeInTheDocument();
    expect(screen.queryByText('Сводка различий A')).toBeNull();
  });

  it('a stale diff is cleared while the new request is pending (no old content visible)', async () => {
    let resolvePending: ((v: unknown) => void) | null = null;
    getMock.mockImplementation((url: string) => {
      if (url.includes('/5/diff') && url.includes('v1=2')) {
        return new Promise((resolve) => { resolvePending = resolve; });
      }
      return Promise.resolve({ data: diffA });
    });

    const view = render(
      <ThemeProvider>
        <EMRDiffViewer visitId={5} versionFrom={1} versionTo={2} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Сводка различий A')).toBeInTheDocument());

    // Request a new comparison; it stays pending.
    view.rerender(
      <ThemeProvider>
        <EMRDiffViewer visitId={5} versionFrom={2} versionTo={3} />
      </ThemeProvider>,
    );
    // Pre-fix: the old diff stayed visible until the new one SUCCEEDED.
    expect(screen.queryByText('Сводка различий A')).toBeNull();
    expect(screen.getByText(/Загрузка/)).toBeInTheDocument();

    await act(async () => { resolvePending?.({ data: diffB }); await flush(); });
    expect(screen.getByText('Сводка различий B')).toBeInTheDocument();
  });

  it('a late FAILURE of the superseded request cannot replace the new result', async () => {
    let rejectA: ((reason?: unknown) => void) | null = null;
    getMock.mockImplementation((url: string) => {
      if (url.includes('/5/diff')) {
        return new Promise((_resolve, reject) => { rejectA = reject; });
      }
      return Promise.resolve({ data: diffB });
    });

    const view = render(
      <ThemeProvider>
        <EMRDiffViewer visitId={5} versionFrom={1} versionTo={2} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    view.rerender(
      <ThemeProvider>
        <EMRDiffViewer visitId={6} versionFrom={1} versionTo={2} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(screen.getByText('Сводка различий B')).toBeInTheDocument());

    await act(async () => { rejectA?.(new Error('late A diff failure')); await flush(); });
    expect(screen.getByText('Сводка различий B')).toBeInTheDocument();
    expect(screen.queryByText(/Не удалось загрузить сравнение/)).toBeNull();
  });
});
