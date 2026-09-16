/**
 * RQ-13 UI-slice (S-11 browser, D-06): the DepartmentManagement panel must
 * TELL the operator what a department status change does before it happens.
 *
 * D-06 owner wording (APPROVED 2026-09-15): deactivation blocks new entries,
 * hides the registrar tab + public QR page, and KEEPS today's waiting
 * patients serviceable until end of day; reactivation restores ONLY the
 * department's own 1:1 profile (independently archived profiles stay
 * archived — D-02 coherence). Deletion of a department whose linked
 * profiles still own queue history is rejected by the backend with 409
 * `department_has_queue_history` + live impact; the panel must surface
 * that impact instead of a generic failure toast.
 *
 * The three distinguishable actions ("скрыть вкладку", "закрыть новую
 * запись", "ожидающие не исчезают") must appear in the deactivation
 * confirmation — one contract, not two behaviors (S-11).
 */
import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import DepartmentManagement from '../DepartmentManagement';
import { api } from '@/api/client';
import { toast } from 'react-toastify';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('react-toastify', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

const mockedGet = vi.mocked(api.get);
const mockedPut = vi.mocked(api.put);
const mockedPatch = vi.mocked(api.patch);
const mockedDelete = vi.mocked(api.delete);

const departmentsFixture = [
  {
    id: 1,
    key: 'cardiology',
    name_ru: 'Кардиология SYNTH',
    name_uz: 'Kardiologiya SYNTH',
    active: true,
    display_order: 1,
    color: '#ffffff',
    icon: '🏥',
    description: '',
    stats: {},
    integrations: {},
  },
  {
    id: 2,
    key: 'dermatology',
    name_ru: 'Дерматология SYNTH',
    name_uz: 'Dermatologiya SYNTH',
    active: false,
    display_order: 2,
    color: '#ffffff',
    icon: '🏥',
    description: '',
    stats: {},
    integrations: {},
  },
];

const renderPanel = () =>
  render(
    <ThemeProvider>
      <DepartmentManagement />
    </ThemeProvider>,
  );

const flipSwitch = async (user: ReturnType<typeof userEvent.setup>, index: number) => {
  const switches = screen.getAllByRole('switch');
  const target = switches[index];
  // The macos Switch input has pointer-events:none; the wrapping <label>
  // is the click surface and forwards activation to the input.
  const label = target.closest('label');
  expect(label).not.toBeNull();
  await user.click(label as HTMLElement);
};

describe('DepartmentManagement department lifecycle consequences (RQ-13 UI, S-11)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGet.mockImplementation(async (url: string) => {
      if (String(url).startsWith('/admin/departments/overview')) {
        return { data: { data: { departments: [], totals: {} } } } as never;
      }
      if (String(url).startsWith('/admin/departments')) {
        return { data: { data: departmentsFixture, count: 2 } } as never;
      }
      return { data: {} } as never;
    });
    mockedPut.mockResolvedValue({ data: { success: true } } as never);
    mockedPatch.mockResolvedValue({ data: { success: true } } as never);
    mockedDelete.mockResolvedValue({ data: { success: true } } as never);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('asks for confirmation before deactivating and lists the three D-06 consequences', async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText('Кардиология SYNTH', {}, { timeout: 5000 });

    await flipSwitch(user, 0); // active → deactivate

    expect((await screen.findAllByText(/Отключить направление\?/)).length).toBeGreaterThan(0);
    // The three distinguishable consequences (S-11 различение):
    expect(await screen.findByText(/закрыть новую запись/i)).toBeInTheDocument();
    expect(await screen.findByText(/скрыть вкладку/i)).toBeInTheDocument();
    expect(await screen.findByText(/ожидающие не исчезают/i)).toBeInTheDocument();
    expect(mockedPut).not.toHaveBeenCalled();
  });

  it('does not deactivate when the confirmation is cancelled', async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText('Кардиология SYNTH', {}, { timeout: 5000 });

    await flipSwitch(user, 0);
    await screen.findAllByText(/Отключить направление\?/);
    await user.click(screen.getAllByRole('button', { name: 'Отмена' })[0]);

    await waitFor(() => {
      expect(screen.queryAllByText(/Отключить направление\?/)).toHaveLength(0);
    });
    expect(mockedPut).not.toHaveBeenCalled();
  });

  it('deactivates after confirmation via the single PUT contract', async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText('Кардиология SYNTH', {}, { timeout: 5000 });

    await flipSwitch(user, 0);
    await screen.findAllByText(/Отключить направление\?/);
    await user.click(await screen.findByRole('button', { name: 'Отключить' }));

    await waitFor(() => {
      expect(mockedPut).toHaveBeenCalledWith('/admin/departments/1', { active: false });
    });
  });

  it('reactivation dialog explains the 1:1 restore semantics before enabling', async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText('Дерматология SYNTH', {}, { timeout: 5000 });

    await flipSwitch(user, 1); // inactive → reactivate

    expect((await screen.findAllByText(/Включить направление\?/)).length).toBeGreaterThan(0);
    expect(
      await screen.findByText(/заархивированные вкладки не включаются/i),
    ).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: 'Включить' }));
    await waitFor(() => {
      expect(mockedPut).toHaveBeenCalledWith('/admin/departments/2', { active: true });
    });
  });

  it('bulk deactivation requires the consequence confirmation', async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText('Кардиология SYNTH', {}, { timeout: 5000 });

    // select the first row checkbox
    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[1]); // index 0 = header select-all
    await user.click(await screen.findByRole('button', { name: /Деактивировать/i }));

    expect((await screen.findAllByText(/Отключить направление\?/)).length).toBeGreaterThan(0);
    expect(mockedPatch).not.toHaveBeenCalled();
    await user.click(await screen.findByRole('button', { name: 'Отключить' }));
    await waitFor(() => {
      expect(mockedPatch).toHaveBeenCalledWith('/admin/departments/bulk-activate', {
        ids: [1],
        active: false,
      });
    });
  });

  it('surfaces the 409 delete-block impact instead of a generic error', async () => {
    const user = userEvent.setup();
    mockedDelete.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            error: 'department_has_queue_history',
            message: 'Нельзя удалить отделение',
            waiting_patients: 3,
            profiles: [
              {
                profile_key: 'cardiology',
                daily_queues: 1,
                entries_waiting: 3,
                entries_total: 5,
              },
            ],
          },
        },
      },
    });
    renderPanel();
    await screen.findByText('Кардиология SYNTH', {}, { timeout: 5000 });

    await user.click(await screen.findByRole('button', { name: /Delete department Кардиология SYNTH/i }));
    await user.click(await screen.findByRole('button', { name: 'Удалить' }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalled();
    });
    const call = vi.mocked(toast.error).mock.calls[0][0];
    const text = typeof call === 'string' ? call : JSON.stringify(call);
    expect(text).toContain('3');
    expect(text).toMatch(/Отключите отделение вместо удаления/i);
  });

  it('tells the operator that renaming syncs the 1:1 profile title', async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText('Кардиология SYNTH', {}, { timeout: 5000 });

    await user.click(await screen.findByRole('button', { name: /Edit department Кардиология SYNTH/i }));
    expect(
      await screen.findByText(/синхронизирует название/i),
    ).toBeInTheDocument();
  });
});
