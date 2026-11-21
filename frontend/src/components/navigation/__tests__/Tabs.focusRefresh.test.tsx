import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ResolvedRegistrarTab, RegistrarTabsResponse } from '../../../api/registrarTabs';
import Tabs from '../Tabs';

vi.mock('../../../api/registrarTabs', () => ({ getRegistrarTabs: vi.fn() }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../../utils/logger', () => ({ default: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), log: vi.fn() } }));
import { getRegistrarTabs } from '../../../api/registrarTabs';

const profile = (id: number, key: string): ResolvedRegistrarTab => ({
  target_kind: 'profile', target_id: id, custom_title: null, title: `SYNTHETIC ${key}`,
  title_ru: null, profile_key: key, queue_tags: [key], icon: 'Heart', color: null,
  visible: true, available: true, reason_code: null,
});
const baselineTabs = [profile(1, 'cardio'), profile(2, 'lab')];
const response = (tabs: ResolvedRegistrarTab[] = baselineTabs): RegistrarTabsResponse => ({
  mode: 'configured', version: 1, tabs,
  profile_filters: tabs.filter((tab) => tab.target_kind === 'profile').map((tab) => ({
    key: tab.profile_key!, title: tab.title, title_ru: tab.title_ru, queue_tags: tab.queue_tags,
  })),
});
const setVisibility = (value: Document['visibilityState']) =>
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => value });
const dispatch = (name: string, target: EventTarget = window) => act(() => { target.dispatchEvent(new Event(name)); });
const callCount = () => vi.mocked(getRegistrarTabs).mock.calls.length;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getRegistrarTabs).mockResolvedValue(response());
  setVisibility('visible');
});
afterEach(() => { cleanup(); setVisibility('visible'); });

describe('unified Registrar tabs revalidation', () => {
  it.each(['focus', 'online', 'registrar:session-refresh'])('refreshes on %s and throttles the return-to-session burst', async (name) => {
    render(<Tabs />);
    await screen.findByRole('tab', { name: 'SYNTHETIC cardio' });
    dispatch(name);
    dispatch('focus');
    dispatch('visibilitychange', document);
    await waitFor(() => expect(callCount()).toBe(2));
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 25)); });
    expect(callCount()).toBe(2);
  });

  it('refreshes when the document becomes visible and ignores hidden returns', async () => {
    render(<Tabs />);
    await screen.findByRole('tab', { name: 'SYNTHETIC cardio' });
    setVisibility('hidden');
    dispatch('focus');
    dispatch('visibilitychange', document);
    expect(callCount()).toBe(1);
    setVisibility('visible');
    dispatch('visibilitychange', document);
    await waitFor(() => expect(callCount()).toBe(2));
  });

  it.each(['registrar-tabs:updated', 'queue-profiles:updated', 'departments:updated'])(
    'accepts the %s compatibility refresh event',
    async (name) => {
      render(<Tabs />);
      await screen.findByRole('tab', { name: 'SYNTHETIC cardio' });
      vi.mocked(getRegistrarTabs).mockResolvedValue(response([...baselineTabs, profile(3, 'derma')]));
      dispatch(name);
      expect(await screen.findByRole('tab', { name: 'SYNTHETIC derma' })).toBeVisible();
    },
  );

  it('keeps the last successful strip and selection after a failed refresh, then retries', async () => {
    const onTabChange = vi.fn();
    render(<Tabs activeTab="cardio" onTabChange={onTabChange} />);
    const first = await screen.findByRole('tab', { name: 'SYNTHETIC cardio' });
    vi.mocked(getRegistrarTabs).mockRejectedValue(new Error('offline'));
    dispatch('focus');
    expect(await screen.findByRole('alert')).toBeVisible();
    expect(first).toHaveAttribute('aria-selected', 'true');
    expect(onTabChange).not.toHaveBeenCalled();
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([profile(4, 'new')]));
    fireEvent.click(screen.getByRole('button', { name: 'registrarPanel.rt_retry' }));
    expect(await screen.findByRole('tab', { name: 'SYNTHETIC new' })).toBeVisible();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('registrarPanel.rt_hidden_filter')).toBeVisible();
  });

  it('accepts a confirmed empty registry and preserves the old filter visibly', async () => {
    const onTabChange = vi.fn();
    render(<Tabs activeTab="cardio" onTabChange={onTabChange} />);
    await screen.findByRole('tab', { name: 'SYNTHETIC cardio' });
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([]));
    dispatch('registrar-tabs:updated');
    expect(await screen.findByText('registrarPanel.rt_hidden_filter')).toBeVisible();
    expect(screen.queryAllByRole('tab')).toHaveLength(0);
    expect(onTabChange).not.toHaveBeenCalled();
  });

  it('ignores an older response that resolves after a newer configuration', async () => {
    let resolveOld: (value: RegistrarTabsResponse) => void = () => {};
    const old = new Promise<RegistrarTabsResponse>((resolve) => { resolveOld = resolve; });
    vi.mocked(getRegistrarTabs).mockReturnValueOnce(old).mockResolvedValue(response([profile(8, 'newest')]));
    render(<Tabs />);
    await waitFor(() => expect(callCount()).toBe(1));
    dispatch('registrar-tabs:updated');
    await screen.findByRole('tab', { name: 'SYNTHETIC newest' });
    await act(async () => { resolveOld(response([profile(9, 'obsolete')])); await old; });
    expect(screen.queryByRole('tab', { name: 'SYNTHETIC obsolete' })).toBeNull();
    expect(screen.getByRole('tab', { name: 'SYNTHETIC newest' })).toBeVisible();
  });

  it('does not publish a late response after unmount', async () => {
    let resolve: (value: RegistrarTabsResponse) => void = () => {};
    const pending = new Promise<RegistrarTabsResponse>((done) => { resolve = done; });
    vi.mocked(getRegistrarTabs).mockReturnValue(pending);
    const onProfilesLoaded = vi.fn();
    const { unmount } = render(<Tabs onProfilesLoaded={onProfilesLoaded} />);
    await waitFor(() => expect(callCount()).toBe(1));
    unmount();
    await act(async () => { resolve(response()); await pending; });
    expect(onProfilesLoaded).not.toHaveBeenCalled();
    dispatch('registrar-tabs:updated');
    expect(callCount()).toBe(1);
  });
});
