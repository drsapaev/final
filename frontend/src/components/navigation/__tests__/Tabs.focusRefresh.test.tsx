/**
 * RQ-27.a (F-23, S-28) — cross-session queue-profile revalidation on the
 * registrar tab strip.
 *
 * The tab strip loads profiles once on mount and afterwards only reacts to
 * same-context window events (`queue-profiles:updated`,
 * `departments:updated`). Those events never cross browser contexts, so a
 * profile created/renamed/disabled by an administrator in ANOTHER session
 * stayed invisible here until a full page reload.
 *
 * The fix: when the user returns to the session (visibilitychange → visible,
 * window focus), `loadQueueProfiles` runs again. The 5s throttle collapses
 * the focus+visibilitychange burst into one refresh; `loadQueueProfiles`
 * already replaces state only on success, so a failed refresh keeps the
 * current tabs.
 */
import { act, cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Tabs from '../Tabs';

vi.mock('../../../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../../utils/logger', () => ({ default: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), log: vi.fn() } }));

import { api } from '../../../api/client';

const PROFILES_RESPONSE = {
  data: {
    success: true,
    source: 'database',
    profiles: [
      { key: 'cardio', title: 'Cardio SYNTHETIC', title_ru: 'Кардио SYNTHETIC', queue_tags: ['cardio'], icon: 'Heart', color: 'var(--mac-error)' },
      { key: 'lab', title: 'Lab SYNTHETIC', title_ru: 'Лаборатория SYNTHETIC', queue_tags: ['lab'], icon: 'FlaskConical', color: 'var(--mac-success)' },
    ],
  },
};

const profilesCallCount = () =>
  vi.mocked(api.get).mock.calls.filter(([url]) => String(url).includes('/queues/profiles')).length;

const setDocumentVisibility = (value: Document['visibilityState']) => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => value });
};

const fireVisibilityChange = () => {
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'));
  });
};

const fireWindowFocus = () => {
  act(() => {
    window.dispatchEvent(new Event('focus'));
  });
};

describe('Tabs — RQ-27.a silent revalidation on return to the session', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.get).mockResolvedValue(PROFILES_RESPONSE);
    setDocumentVisibility('visible');
  });

  afterEach(() => {
    cleanup();
    setDocumentVisibility('visible');
  });

  it('reloads queue profiles when the session becomes visible again', async () => {
    render(<Tabs />);
    await waitFor(() => {
      expect(profilesCallCount()).toBe(1);
    });

    fireVisibilityChange();

    await waitFor(() => {
      expect(profilesCallCount()).toBe(2);
    });
  });

  it('reloads on window focus and throttles the focus+visibility burst to one refresh', async () => {
    render(<Tabs />);
    await waitFor(() => {
      expect(profilesCallCount()).toBe(1);
    });

    fireWindowFocus();
    fireVisibilityChange();

    await waitFor(() => {
      expect(profilesCallCount()).toBe(2);
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    expect(profilesCallCount()).toBe(2);
  });

  it('keeps the rendered tab strip when the silent revalidation fails', async () => {
    const { container } = render(<Tabs />);
    await waitFor(() => {
      expect(profilesCallCount()).toBe(1);
    });
    const before = container.querySelectorAll('.tab-button.department').length;
    expect(before).toBeGreaterThan(0);

    vi.mocked(api.get).mockRejectedValue(new Error('offline during revalidation'));
    fireVisibilityChange();

    await waitFor(() => {
      expect(profilesCallCount()).toBe(2);
    });
    // A failed revalidation must not blank the strip (existing success-only
    // replace semantics; the offline fallback set is the documented path).
    expect(container.querySelectorAll('.tab-button.department').length).toBeGreaterThan(0);
  });

  it('does not revalidate while the document is hidden', async () => {
    render(<Tabs />);
    await waitFor(() => {
      expect(profilesCallCount()).toBe(1);
    });

    setDocumentVisibility('hidden');
    fireVisibilityChange();
    fireWindowFocus();

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    expect(profilesCallCount()).toBe(1);
  });
});
