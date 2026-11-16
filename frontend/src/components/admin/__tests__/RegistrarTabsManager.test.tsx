import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RegistrarTabsManager from '../RegistrarTabsManager';
import type { AdminRegistrarTabsResponse, ResolvedRegistrarTab } from '../../../api/registrarTabs';

const apiMocks = vi.hoisted(() => ({ load: vi.fn(), save: vi.fn() }));

vi.mock('../../../api/registrarTabs', () => ({
  getAdminRegistrarTabs: apiMocks.load,
  saveRegistrarTabs: apiMocks.save,
  registrarTabIdentity: (tab: { target_kind: string; target_id: number }) => `${tab.target_kind}:${tab.target_id}`,
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'en',
    t: (key: string, options?: { name?: string }) => options?.name ? `${key} ${options.name}` : key,
  }),
}));

vi.mock('../QueueProfilesManager', () => ({ default: () => <div>profile-editor</div> }));

const direction: ResolvedRegistrarTab = {
  target_kind: 'profile', target_id: 7, custom_title: null, title: 'SYNTHETIC Direction', title_ru: null,
  profile_key: 'synthetic', queue_tags: ['synthetic'], icon: 'Heart', color: null,
  visible: true, available: true, reason_code: null,
};
const doctor: ResolvedRegistrarTab = {
  target_kind: 'doctor', target_id: 7, custom_title: null, title: 'SYNTHETIC Doctor', title_ru: null,
  profile_key: null, queue_tags: [], icon: null, color: null,
  visible: true, available: true, reason_code: null,
};
const otherDoctor: ResolvedRegistrarTab = { ...doctor, target_id: 9, title: 'SYNTHETIC Other Doctor' };

const configuration = (tabs = [direction, doctor], mode: 'legacy' | 'configured' = 'legacy'): AdminRegistrarTabsResponse => ({
  mode, version: mode === 'legacy' ? 0 : 2, tabs: tabs.map((tab) => ({ ...tab })),
  profile_filters: [{ key: 'synthetic', queue_tags: ['synthetic'], title: 'SYNTHETIC Direction', title_ru: null }],
  options: [direction, doctor, otherDoctor].map((tab) => ({ ...tab })),
});

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.load.mockResolvedValue(configuration());
  apiMocks.save.mockImplementation(async (request: { tabs: Array<{ target_kind: string; target_id: number; title: string | null; visible: boolean }> }) => {
    const options = [direction, doctor, otherDoctor];
    return {
      ...configuration([], 'configured'),
      tabs: request.tabs.map((tab) => {
        const target = options.find((option) => option.target_kind === tab.target_kind && option.target_id === tab.target_id);
        if (!target) throw new Error('Unknown synthetic tab');
        return { ...target, visible: tab.visible, custom_title: tab.title, title: tab.title || target.title };
      }),
    };
  });
});

describe('RegistrarTabsManager', () => {
  it('edits and saves one mixed ordered list without changing target identity', async () => {
    const user = userEvent.setup();
    render(<RegistrarTabsManager />);
    expect(await screen.findByText('registrarPanel.rt_legacy_notice')).toBeInTheDocument();
    expect(screen.getByText('registrarPanel.rt_all_departments')).toBeInTheDocument();
    await user.clear(screen.getByRole('textbox', { name: 'registrarPanel.rt_name_label SYNTHETIC Direction — registrarPanel.rt_profile · #7' }));
    await user.type(screen.getByRole('textbox', { name: 'registrarPanel.rt_name_label SYNTHETIC Direction — registrarPanel.rt_profile · #7' }), 'SYNTHETIC Front Desk');
    await user.click(screen.getByRole('checkbox', { name: 'registrarPanel.rt_visible_label SYNTHETIC Doctor — registrarPanel.rt_doctor · #7' }));
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_move_up_label SYNTHETIC Doctor — registrarPanel.rt_doctor · #7' }));
    expect(screen.getAllByRole('textbox').map((input) => (input as HTMLInputElement).value)).toEqual(['SYNTHETIC Doctor', 'SYNTHETIC Front Desk']);
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_save' }));
    await waitFor(() => expect(apiMocks.save).toHaveBeenCalledWith({
      expected_version: 0,
      reason: 'configure_registrar_tabs',
      tabs: [
        { target_kind: 'doctor', target_id: 7, title: null, visible: false },
        { target_kind: 'profile', target_id: 7, title: 'SYNTHETIC Front Desk', visible: true },
      ],
    }));
    expect(await screen.findByText('registrarPanel.rt_saved')).toBeInTheDocument();
  });

  it('saves an explicitly empty list after removing every configured tab', async () => {
    const user = userEvent.setup();
    render(<RegistrarTabsManager />);
    await screen.findByDisplayValue('SYNTHETIC Direction');
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_remove_label SYNTHETIC Direction — registrarPanel.rt_profile · #7' }));
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_remove_label SYNTHETIC Doctor — registrarPanel.rt_doctor · #7' }));
    expect(screen.getByText('registrarPanel.rt_empty')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_save' }));
    await waitFor(() => expect(apiMocks.save).toHaveBeenCalledWith({ expected_version: 0, tabs: [], reason: 'configure_registrar_tabs' }));
    expect(await screen.findByText('registrarPanel.rt_saved')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('adds only an available unused typed target through the single selector', async () => {
    const user = userEvent.setup();
    render(<RegistrarTabsManager />);
    await screen.findByDisplayValue('SYNTHETIC Direction');
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_add_target' }));
    expect(screen.queryByRole('option', { name: 'SYNTHETIC Doctor · #7 — registrarPanel.rt_doctor' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('option', { name: 'SYNTHETIC Other Doctor · #9 — registrarPanel.rt_doctor' }));
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_add' }));
    expect(screen.getAllByRole('textbox')).toHaveLength(3);
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_save' }));
    await waitFor(() => expect(apiMocks.save).toHaveBeenCalledWith(expect.objectContaining({
      tabs: expect.arrayContaining([{ target_kind: 'doctor', target_id: 9, title: null, visible: true }]),
    })));
  });

  it('preserves the draft on a stale save and reloads only after an explicit discard action', async () => {
    const user = userEvent.setup();
    apiMocks.save.mockRejectedValue({ response: { status: 409 } });
    render(<RegistrarTabsManager />);
    const input = await screen.findByDisplayValue('SYNTHETIC Direction');
    fireEvent.change(input, { target: { value: 'SYNTHETIC Draft' } });
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('registrarPanel.rt_conflict');
    expect(screen.getByDisplayValue('SYNTHETIC Draft')).toBeInTheDocument();
    expect(screen.queryByText('registrarPanel.rt_saved')).not.toBeInTheDocument();
    apiMocks.load.mockResolvedValue(configuration([otherDoctor], 'configured'));
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_discard_reload' }));
    expect(await screen.findByDisplayValue('SYNTHETIC Other Doctor')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('SYNTHETIC Draft')).not.toBeInTheDocument();
  });

  it('distinguishes a failed read from an empty configuration and can retry', async () => {
    const user = userEvent.setup();
    apiMocks.load.mockRejectedValueOnce(new Error('Synthetic network failure'));
    render(<RegistrarTabsManager />);
    expect(await screen.findByRole('alert')).toHaveTextContent('registrarPanel.rt_load_error');
    expect(screen.queryByText('registrarPanel.rt_empty')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'registrarPanel.rt_save' })).toBeDisabled();
    apiMocks.load.mockResolvedValue(configuration([], 'configured'));
    await user.click(screen.getByRole('button', { name: 'registrarPanel.rt_retry' }));
    expect(await screen.findByText('registrarPanel.rt_empty')).toBeInTheDocument();
  });

  it('keeps unavailable configured targets visible to the administrator for repair', async () => {
    apiMocks.load.mockResolvedValue(configuration([{ ...doctor, available: false, reason_code: 'target_missing' }], 'configured'));
    render(<RegistrarTabsManager />);
    expect(await screen.findByText('registrarPanel.rt_unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'registrarPanel.rt_remove_label SYNTHETIC Doctor — registrarPanel.rt_doctor · #7' })).toBeEnabled();
  });
});
