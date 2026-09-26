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

// RQ-27.b (S-28): network restoration and the panel manual-refresh button
// both run the same throttled silent revalidation.
const fireOnline = () => {
  act(() => {
    window.dispatchEvent(new Event('online'));
  });
};

const fireSessionRefresh = () => {
  act(() => {
    window.dispatchEvent(new CustomEvent('registrar:session-refresh'));
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

  // ── RQ-27.b: integration of a NEW direction + understandable disable ──

  it('picks up a NEW direction created in another session on revalidation', async () => {
    const onProfilesLoaded = vi.fn();
    const { container } = render(<Tabs onProfilesLoaded={onProfilesLoaded} />);
    await waitFor(() => {
      expect(profilesCallCount()).toBe(1);
    });
    expect(container.querySelectorAll('.tab-button.department')).toHaveLength(2);
    expect(onProfilesLoaded).toHaveBeenLastCalledWith(expect.objectContaining({ length: 2 }));

    // An administrator created a third profile in ANOTHER session: the
    // silent revalidation integrates it as a new tab without any reload.
    const THREE_PROFILES = {
      data: {
        success: true,
        source: 'database',
        profiles: [
          ...PROFILES_RESPONSE.data.profiles,
          { key: 'derma', title: 'Derma SYNTHETIC', title_ru: 'Дерма SYNTHETIC', queue_tags: ['derma'], icon: 'UserCheck', color: 'var(--mac-warning)' },
        ],
      },
    };
    vi.mocked(api.get).mockResolvedValue(THREE_PROFILES);
    fireVisibilityChange();

    await waitFor(() => {
      expect(container.querySelectorAll('.tab-button.department')).toHaveLength(3);
    });
    expect(container.querySelector('[data-tab="derma"]')).not.toBeNull();
    expect(onProfilesLoaded).toHaveBeenLastCalledWith(expect.objectContaining({ length: 3 }));
  });

  it('falls back to all departments when the ACTIVE tab is disabled in another session', async () => {
    const onTabChange = vi.fn();
    const { container } = render(<Tabs activeTab="cardio" onTabChange={onTabChange} />);
    await waitFor(() => {
      expect(profilesCallCount()).toBe(1);
    });
    expect(container.querySelector('[data-tab="cardio"]')).not.toBeNull();

    // The active profile was disabled in ANOTHER session: the revalidation
    // must not leave the registrar silently sitting on a stale empty filter —
    // the understandable outcome is the all-departments view.
    vi.mocked(api.get).mockResolvedValue({
      data: {
        success: true,
        source: 'database',
        profiles: [PROFILES_RESPONSE.data.profiles[1]], // only 'lab' remains
      },
    });
    fireVisibilityChange();

    await waitFor(() => {
      expect(onTabChange).toHaveBeenCalledWith(null);
    });
    expect(container.querySelector('[data-tab="cardio"]')).toBeNull();
  });

  it('never deselects the active tab on a FAILED revalidation', async () => {
    const onTabChange = vi.fn();
    render(<Tabs activeTab="cardio" onTabChange={onTabChange} />);
    await waitFor(() => {
      expect(profilesCallCount()).toBe(1);
    });

    vi.mocked(api.get).mockRejectedValue(new Error('offline during revalidation'));
    fireVisibilityChange();

    await waitFor(() => {
      expect(profilesCallCount()).toBe(2);
    });
    // Success-path-only reset: a failed refresh (fallback set) must not
    // deselect the user's tab.
    expect(onTabChange).not.toHaveBeenCalled();
  });

  it('revalidates on online and manual session-refresh events with one throttle budget', async () => {
    render(<Tabs />);
    await waitFor(() => {
      expect(profilesCallCount()).toBe(1);
    });

    fireOnline();
    await waitFor(() => {
      expect(profilesCallCount()).toBe(2);
    });

    // online + session-refresh + focus within the throttle window = one refresh
    fireOnline();
    fireSessionRefresh();
    fireWindowFocus();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    expect(profilesCallCount()).toBe(2);
  });
});
