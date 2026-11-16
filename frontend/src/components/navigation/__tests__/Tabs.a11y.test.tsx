import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ResolvedRegistrarTab, RegistrarTabsResponse } from '../../../api/registrarTabs';
import { toDoctorId } from '../../../types/domain/branded';

vi.mock('../../../api/registrarTabs', () => ({ getRegistrarTabs: vi.fn() }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../../utils/logger', () => ({ default: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), log: vi.fn() } }));
import Tabs, { doctorTabButtonIdFor, tabButtonIdFor } from '../Tabs';
import { getRegistrarTabs } from '../../../api/registrarTabs';

const profile = (id: number, key: string, title: string, tags = [key]): ResolvedRegistrarTab => ({
  target_kind: 'profile', target_id: id, custom_title: null, title, title_ru: title,
  profile_key: key, queue_tags: tags, icon: 'Heart', color: 'var(--mac-accent)',
  visible: true, available: true, reason_code: null,
});
const doctor = (id: number, title: string): ResolvedRegistrarTab => ({
  target_kind: 'doctor', target_id: id, custom_title: null, title, title_ru: title,
  profile_key: null, queue_tags: [], icon: 'UserCheck', color: null,
  visible: true, available: true, reason_code: null,
});
const standard = [profile(1, 'cardiology', 'SYNTHETIC Cardiology'), profile(2, 'ecg', 'SYNTHETIC ECG')];
const response = (tabs: ResolvedRegistrarTab[] = standard): RegistrarTabsResponse => ({
  mode: 'configured', version: 1, tabs,
  profile_filters: tabs.filter((tab) => tab.target_kind === 'profile').map((tab) => ({
    key: tab.profile_key!, queue_tags: tab.queue_tags, title: tab.title, title_ru: tab.title_ru,
  })),
});
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getRegistrarTabs).mockResolvedValue(response());
});
afterEach(() => cleanup());

describe('unified configured registrar strip', () => {
  it('keeps a saved empty list empty instead of appending doctors from the catalog', async () => {
    const onProfilesLoaded = vi.fn();
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([]));
    render(<Tabs doctors={[{ id: toDoctorId(42), full_name: 'SYNTHETIC Doctor' }]} onProfilesLoaded={onProfilesLoaded} />);
    await waitFor(() => expect(onProfilesLoaded).toHaveBeenCalledWith([]));
    expect(screen.queryAllByRole('tab')).toHaveLength(0);
    expect(screen.getByRole('button', { name: 'queue.all_departments' })).toBeVisible();
  });

  it('preserves configured mixed order and invokes existing typed selection callbacks', async () => {
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([
      doctor(7, 'SYNTHETIC First doctor'), standard[0], doctor(8, 'SYNTHETIC Last doctor'), standard[1],
    ]));
    const onDoctorChange = vi.fn();
    const onTabChange = vi.fn();
    render(<Tabs activeDoctorId={7} onDoctorChange={onDoctorChange} onTabChange={onTabChange} />);
    const first = await screen.findByRole('tab', { name: 'SYNTHETIC First doctor' });
    const tabs = within(screen.getByRole('tablist')).getAllByRole('tab');
    expect(tabs.map((tab) => tab.getAttribute('aria-label'))).toEqual([
      'SYNTHETIC First doctor', 'SYNTHETIC Cardiology', 'SYNTHETIC Last doctor', 'SYNTHETIC ECG',
    ]);
    expect(first.id).toBe(doctorTabButtonIdFor(7));
    expect(first).toHaveAttribute('aria-selected', 'true');
    expect(tabs[1].id).toBe(tabButtonIdFor('cardiology'));
    fireEvent.click(tabs[1]);
    expect(onTabChange).toHaveBeenCalledWith('cardiology');
    fireEvent.click(tabs[2]);
    expect(onDoctorChange).toHaveBeenCalledWith(8);
    fireEvent.click(first);
    expect(onDoctorChange).toHaveBeenCalledWith(null);
  });

  it('keeps a unique accessible name aligned with visible text', async () => {
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([doctor(7, 'SYNTHETIC Same'), doctor(8, 'SYNTHETIC Same')]));
    render(<Tabs />);
    await screen.findByRole('tab', { name: 'SYNTHETIC Same · #7' });
    for (const tab of screen.getAllByRole('tab')) {
      expect(tab).toHaveAttribute('aria-label', tab.querySelector('.tab-label')?.textContent);
      expect(tab).toHaveAttribute('aria-controls', 'main-content');
      expect(tab.id).not.toMatch(/\s/);
    }
    expect(screen.getByRole('button', { name: 'queue.all_departments' })).toHaveTextContent('queue.all_departments');
  });

  it('announces operational statuses as descriptions, including doctor counts', async () => {
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([standard[0], doctor(7, 'SYNTHETIC Doctor')]));
    render(<Tabs departmentStats={{ cardiology: { todayCount: 4, hasActiveQueue: true, hasPendingPayments: true } }}
      doctorStats={{ '7': { todayCount: 2, hasActiveQueue: true } }} doctorCountLabel="SYNTHETIC historical count" />);
    const cardiology = await screen.findByRole('tab', { name: 'SYNTHETIC Cardiology' });
    expect(cardiology).toHaveAccessibleDescription('final.tgs_active_queue, registrarPanel.pending_payments, registrarPanel.today: 4');
    expect(cardiology.querySelector('.status-indicator.queue')).toHaveAttribute('title', 'final.tgs_active_queue');
    expect(cardiology.querySelector('.status-indicator.pending')).toHaveAttribute('title', 'registrarPanel.pending_payments');
    expect(screen.getByRole('tab', { name: 'SYNTHETIC Doctor' })).toHaveAccessibleDescription(
      'final.tgs_active_queue, SYNTHETIC historical count: 2',
    );
  });

  it('encodes whitespace keys in IDs and keeps status descriptions resolvable', async () => {
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([profile(9, 'general medicine', 'SYNTHETIC General')]));
    render(<Tabs departmentStats={{ 'general medicine': { todayCount: 2 } }} />);
    const tab = await screen.findByRole('tab', { name: 'SYNTHETIC General' });
    expect(tab.id).toBe(tabButtonIdFor('general medicine'));
    const descriptionId = tab.getAttribute('aria-describedby')!;
    expect(descriptionId).not.toMatch(/\s/);
    expect(tab.contains(document.getElementById(descriptionId))).toBe(true);
    expect(tab).toHaveAccessibleDescription('registrarPanel.today: 2');
  });

  it('has no dangling status description for rows with no statistics', async () => {
    render(<Tabs />);
    await screen.findByRole('tab', { name: 'SYNTHETIC Cardiology' });
    screen.getAllByRole('tab').forEach((tab) => expect(tab).not.toHaveAttribute('aria-describedby'));
  });

  it('supports manual keyboard navigation through mixed targets without changing selection', async () => {
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([standard[0], doctor(7, 'SYNTHETIC Doctor'), standard[1]]));
    const onDoctorChange = vi.fn();
    const onTabChange = vi.fn();
    render(<Tabs activeTab="cardiology" onDoctorChange={onDoctorChange} onTabChange={onTabChange} />);
    await screen.findByRole('tab', { name: 'SYNTHETIC Doctor' });
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((tab) => tab.getAttribute('tabindex'))).toEqual(['0', '-1', '-1']);
    tabs[0].focus();
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
    expect(tabs[1]).toHaveFocus();
    fireEvent.keyDown(tabs[1], { key: 'End' });
    expect(tabs[2]).toHaveFocus();
    fireEvent.keyDown(tabs[2], { key: 'ArrowRight' });
    expect(tabs[0]).toHaveFocus();
    fireEvent.keyDown(tabs[0], { key: 'ArrowLeft' });
    expect(tabs[2]).toHaveFocus();
    fireEvent.keyDown(tabs[2], { key: 'Home' });
    expect(tabs[0]).toHaveFocus();
    expect(onDoctorChange).not.toHaveBeenCalled();
    expect(onTabChange).not.toHaveBeenCalled();
    expect(document.querySelector('.tab-indicator')).toHaveAttribute('aria-hidden', 'true');
  });

  it('keeps all unselected tabs tabbable for the all-departments view', async () => {
    render(<Tabs />);
    await screen.findByRole('tab', { name: 'SYNTHETIC ECG' });
    screen.getAllByRole('tab').forEach((tab) => expect(tab).toHaveAttribute('tabindex', '0'));
  });

  it('notifies the parent with metadata for hidden profile deep links without rendering it', async () => {
    const onProfilesLoaded = vi.fn();
    const payload = response([standard[1], doctor(7, 'SYNTHETIC Doctor')]);
    payload.profile_filters.push({ key: 'hidden', queue_tags: ['alias'], title: 'SYNTHETIC Hidden', title_ru: null });
    vi.mocked(getRegistrarTabs).mockResolvedValue(payload);
    render(<Tabs onProfilesLoaded={onProfilesLoaded} />);
    await screen.findByRole('tab', { name: 'SYNTHETIC ECG' });
    expect(onProfilesLoaded).toHaveBeenLastCalledWith(expect.arrayContaining([
      expect.objectContaining({ key: 'hidden', queue_tags: ['alias'] }),
    ]));
    expect(screen.queryByRole('tab', { name: 'SYNTHETIC Hidden' })).toBeNull();
    expect(onProfilesLoaded.mock.calls[0][0]).not.toEqual(expect.arrayContaining([expect.objectContaining({ key: 'doctor:7' })]));
  });

  it.each(['profile', 'doctor'] as const)('preserves a hidden %s filter until the user explicitly clears it', async (kind) => {
    vi.mocked(getRegistrarTabs).mockResolvedValue(response([]));
    const onTabChange = vi.fn();
    const onDoctorChange = vi.fn();
    const selectedLabelId = kind === 'profile' ? tabButtonIdFor('hidden') : doctorTabButtonIdFor(7);
    render(<>
      <Tabs activeTab={kind === 'profile' ? 'hidden' : null} activeDoctorId={kind === 'doctor' ? 7 : null}
        onTabChange={onTabChange} onDoctorChange={onDoctorChange} />
      <div role="tabpanel" aria-labelledby={selectedLabelId}>SYNTHETIC historical worklist</div>
    </>);
    const hiddenFilterLabel = await screen.findByText('registrarPanel.rt_hidden_filter');
    expect(hiddenFilterLabel).toBeVisible();
    expect(hiddenFilterLabel).toHaveAttribute('id', selectedLabelId);
    expect(screen.getByRole('tabpanel')).toHaveAccessibleName('registrarPanel.rt_hidden_filter');
    expect(screen.queryAllByRole('tab')).toHaveLength(0);
    expect(screen.getByRole('tablist')).not.toContainElement(hiddenFilterLabel);
    expect(onTabChange).not.toHaveBeenCalled();
    expect(onDoctorChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'registrarPanel.rt_clear_filter' }));
    if (kind === 'profile') expect(onTabChange).toHaveBeenCalledWith(null);
    else expect(onDoctorChange).toHaveBeenCalledWith(null);
  });

  it('does not assert that a filter is hidden before the initial response or after initial failure', async () => {
    vi.mocked(getRegistrarTabs).mockRejectedValue(new Error('offline'));
    render(<Tabs activeDoctorId={7} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('registrarPanel.rt_load_error');
    expect(screen.queryByText('registrarPanel.rt_hidden_filter')).toBeNull();
    expect(screen.getByRole('button', { name: 'registrarPanel.rt_retry' })).toBeVisible();
  });

  it('status keys resolve in the existing locale resources for all five locales', () => {
    const fs = require('node:fs') as typeof import('node:fs');
    const path = require('node:path') as typeof import('node:path');
    for (const locale of ['ru', 'en', 'kk', 'uz-Cyrl', 'uz-Latn']) {
      const src = fs.readFileSync(path.resolve(__dirname, `../../../i18n/locales/${locale}.ts`), 'utf8');
      for (const key of ['tgs_active_queue', 'pending_payments', 'today']) {
        expect(src).toMatch(new RegExp(`\\b${key}: ['"]`));
      }
    }
  });
});
