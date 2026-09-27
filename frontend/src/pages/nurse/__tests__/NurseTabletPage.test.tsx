/**
 * NURSE-V2 N2-5 — the tablet workspace component suite.
 *
 * Covers the §13 required scenarios: workplace states (0/1/N), the
 * waiting board, the current patient (called / in_progress services),
 * double-tap guarding, the 409/403/network error contracts, the
 * mandatory-reason dialog UX, and the "no Visit-close action" pin.
 * The API module is mocked at the boundary; the state machine under
 * test is useNurseServingBoard + the real components.
 */

import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { StrictMode } from 'react';

import type { NurseStationBoard, NurseWorkplace } from '@/api/nurseServing';

import NurseTabletPage from '../NurseTabletPage';
import { renderWithProviders } from '@/test/renderWithProviders';

// ---------------------------------------------------------------------------
// the API boundary mock (the server contract shapes are reused verbatim)
// ---------------------------------------------------------------------------

const workplacesMock = vi.fn();
const boardMock = vi.fn();
const drainingMock = vi.fn();
const callNextMock = vi.fn();
const startMock = vi.fn();
const startExecutionMock = vi.fn();
const completeExecutionMock = vi.fn();
const incompleteExecutionMock = vi.fn();
const noShowMock = vi.fn();
const entryIncompleteMock = vi.fn();

vi.mock('@/api/nurseServing', async () => {
  const actual = await vi.importActual<
    typeof import('@/api/nurseServing')
  >('@/api/nurseServing');
  return {
    ...actual,
    listWorkplaces: (...args: unknown[]) => workplacesMock(...args),
    getStationBoard: (...args: unknown[]) => boardMock(...args),
    listDrainingExecutions: (...args: unknown[]) => drainingMock(...args),
    callNextPatient: (...args: unknown[]) => callNextMock(...args),
    startEntry: (...args: unknown[]) => startMock(...args),
    startServiceExecution: (...args: unknown[]) => startExecutionMock(...args),
    completeServiceExecution: (...args: unknown[]) =>
      completeExecutionMock(...args),
    incompleteServiceExecution: (...args: unknown[]) =>
      incompleteExecutionMock(...args),
    markEntryNoShow: (...args: unknown[]) => noShowMock(...args),
    markEntryIncomplete: (...args: unknown[]) => entryIncompleteMock(...args),
  };
});

const WORKPLACE_A: NurseWorkplace = {
  assignment_id: 1,
  queue_resource_id: 10,
  resource_code: 'proc',
  resource_display_name: 'Процедурный кабинет',
  resource_queue_tag: 'tag_proc',
  resource_default_cabinet: '4',
  cabinet_override: null,
  effective_cabinet: '4',
};

const WORKPLACE_B: NurseWorkplace = {
  ...WORKPLACE_A,
  assignment_id: 2,
  queue_resource_id: 20,
  resource_code: 'proc2',
  resource_display_name: 'Перевязочная',
  effective_cabinet: '9',
};

const WAITING_BOARD: NurseStationBoard = {
  queue_resource_id: 10,
  resource_queue_tag: 'tag_proc',
  resource_display_name: 'Процедурный кабинет',
  effective_cabinet: '4',
  queue_id: 100,
  queue_day: '2026-09-21T00:00:00Z',
  waiting: [
    {
      id: 11,
      number: 17,
      status: 'waiting',
      priority: 0,
      source: 'desk',
      patient_id: 5,
      patient_name: 'Анна Тестова',
      phone: null,
      queue_time: '2026-09-21T08:00:00Z',
      called_at: null,
      called_by_user_id: null,
      served_by_user_id: null,
      served_at: null,
      visit_id: null,
      is_my_claim: false,
      services: [],
    },
  ],
  active: [],
  my_entry: null,
  late_pending: [],
  counts: { waiting: 1 },
};

const CALLED_BOARD: NurseStationBoard = {
  ...WAITING_BOARD,
  waiting: [],
  counts: { waiting: 0 },
  my_entry: {
    ...WAITING_BOARD.waiting[0],
    id: 11,
    status: 'called',
    called_at: '2026-09-21T08:05:00Z',
    is_my_claim: true,
  },
  active: [
    {
      ...WAITING_BOARD.waiting[0],
      status: 'called',
      is_my_claim: true,
    },
  ],
};

const IN_PROGRESS_BOARD: NurseStationBoard = {
  ...CALLED_BOARD,
  my_entry: {
    ...CALLED_BOARD.my_entry!,
    id: 11,
    status: 'in_progress',
    visit_id: 77,
    services: [
      {
        visit_service_id: 701,
        service_id: 9,
        code: 'INJ01',
        name: 'Инъекция',
        qty: 1,
        latest_attempt_no: null,
        latest_attempt_status: null,
        in_progress_execution_id: null,
        pending: true,
      },
      {
        visit_service_id: 702,
        service_id: 10,
        code: 'DRESS01',
        name: 'Перевязка',
        qty: 1,
        latest_attempt_no: 1,
        latest_attempt_status: null,
        in_progress_execution_id: 55,
        pending: false,
      },
    ],
  },
  active: [
    {
      ...CALLED_BOARD.my_entry!,
      status: 'in_progress',
      visit_id: 77,
      services: [
        {
          visit_service_id: 701,
          service_id: 9,
          code: 'INJ01',
          name: 'Инъекция',
          qty: 1,
          latest_attempt_no: null,
          latest_attempt_status: null,
          in_progress_execution_id: null,
          pending: true,
        },
        {
          visit_service_id: 702,
          service_id: 10,
          code: 'DRESS01',
          name: 'Перевязка',
          qty: 1,
          latest_attempt_no: 1,
          latest_attempt_status: null,
          in_progress_execution_id: 55,
          pending: false,
        },
      ],
    },
  ],
};

function setup({
  workplaces = [WORKPLACE_A],
  board = WAITING_BOARD,
  draining = { items: [], total: 0 },
}: {
  workplaces?: NurseWorkplace[];
  board?: NurseStationBoard | null;
  draining?: { items: unknown[]; total: number };
} = {}) {
  workplacesMock.mockResolvedValue({ items: workplaces, total: workplaces.length });
  boardMock.mockResolvedValue(board);
  drainingMock.mockResolvedValue(draining);
  window.localStorage.clear();
  return renderWithProviders(<NurseTabletPage />, {
    routerProps: { initialEntries: ['/nurse'] },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  window.localStorage.clear();
});

// ---------------------------------------------------------------------------
// §4 workplace UX
// ---------------------------------------------------------------------------

describe('NURSE-V2 N2-5 tablet — workplace UX', () => {
  it('shows the zero-workplace state and never renders queue/patient data', async () => {
    setup({ workplaces: [] });
    expect(await screen.findByText('Нет назначенного рабочего места')).toBeInTheDocument();
    expect(screen.queryByText('Вызвать следующего')).not.toBeInTheDocument();
    expect(boardMock).not.toHaveBeenCalled();
  });

  it('auto-selects the single workplace and loads its board', async () => {
    setup({ workplaces: [WORKPLACE_A] });
    expect(await screen.findByText('Процедурный кабинет')).toBeInTheDocument();
    await waitFor(() => expect(boardMock).toHaveBeenCalledWith(10));
    expect(screen.queryByText('Выберите рабочее место')).not.toBeInTheDocument();
  });

  it('offers the selector for multiple workplaces and switches on choice', async () => {
    const user = userEvent.setup();
    setup({ workplaces: [WORKPLACE_A, WORKPLACE_B] });
    expect(await screen.findByText('Выберите рабочее место')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Перевязочная/ }));
    await waitFor(() => expect(boardMock).toHaveBeenCalledWith(20));
    expect(window.localStorage.getItem('nurse.serving.workplace')).toBe('20');
  });
});

// ---------------------------------------------------------------------------
// §5 the board
// ---------------------------------------------------------------------------

describe('NURSE-V2 N2-5 tablet — station board', () => {
  it('waiting board: renders the next patient and the call-next action', async () => {
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getByText('№ 17')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Вызвать следующего' })).toBeEnabled();
  });

  it('called patient: start / no-show / entry-incomplete actions per server state', async () => {
    setup({ board: CALLED_BOARD });
    expect(await screen.findByText('Текущий пациент')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Начать приём' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Пациент не явился' })).toBeEnabled();
    expect(
      screen.getByRole('button', { name: 'Завершить без выполнения' }),
    ).toBeEnabled();
  });

  it('in_progress patient: per-service actions — start pending, finish active', async () => {
    setup({ board: IN_PROGRESS_BOARD });
    expect(await screen.findByText('Инъекция')).toBeInTheDocument();
    expect(screen.getByText('Перевязка')).toBeInTheDocument();
    // pending service without an execution -> [Начать услугу]
    expect(
      screen.getByRole('button', { name: 'Начать услугу' }),
    ).toBeEnabled();
    // active execution -> [Выполнено] + [Не завершено]
    expect(screen.getAllByRole('button', { name: 'Выполнено' }).length).toBe(1);
    expect(screen.getAllByRole('button', { name: 'Не завершено' }).length).toBe(1);
  });

  it('renders NO visit-close action anywhere', async () => {
    setup({ board: IN_PROGRESS_BOARD });
    await screen.findByText('Инъекция');
    // §5: «Выполнено» completes a ServiceExecution, the Visit is NEVER closed.
    expect(screen.queryByText(/Закрыть визит/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Завершить визит/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Close visit/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// §7 double-tap / idempotency UX
// ---------------------------------------------------------------------------

describe('NURSE-V2 N2-5 tablet — mutation discipline', () => {
  it('disables the pending mutation button and does not double-fire', async () => {
    const user = userEvent.setup();
    let resolveFn: (value: unknown) => void = () => {};
    callNextMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
    );
    setup({ board: WAITING_BOARD });
    const button = await screen.findByRole('button', { name: 'Вызвать следующего' });
    await user.click(button);
    await user.click(button);
    expect(callNextMock).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    resolveFn({
      entry: CALLED_BOARD.my_entry,
      idempotent: false,
      waiting_count: 0,
    });
    await waitFor(() => expect(callNextMock).toHaveBeenCalledTimes(1));
  });

  it('refetches the canonical board after a successful mutation', async () => {
    const user = userEvent.setup();
    callNextMock.mockResolvedValue({
      entry: CALLED_BOARD.my_entry,
      idempotent: false,
      waiting_count: 0,
    });
    setup({ board: WAITING_BOARD });
    await user.click(await screen.findByRole('button', { name: 'Вызвать следующего' }));
    await waitFor(() => expect(boardMock).toHaveBeenCalledTimes(2));
  });

  it('409: surfaces the conflict notice and refetches — no retry loop', async () => {
    const user = userEvent.setup();
    callNextMock.mockRejectedValue({
      response: { status: 409, data: { detail: 'conflict' } },
    });
    setup({ board: WAITING_BOARD });
    await user.click(await screen.findByRole('button', { name: 'Вызвать следующего' }));
    expect(
      await screen.findByText(/Состояние уже изменилось другим сотрудником/),
    ).toBeInTheDocument();
    await waitFor(() => expect(boardMock).toHaveBeenCalledTimes(2));
    expect(callNextMock).toHaveBeenCalledTimes(1);
  });

  it('403: resets the workplace selection and re-reads workplaces', async () => {
    const user = userEvent.setup();
    callNextMock.mockRejectedValue({
      response: { status: 403, data: { detail: 'no assignment' } },
    });
    // second workplaces read returns an EMPTY list (assignment revoked)
    workplacesMock.mockResolvedValueOnce({ items: [WORKPLACE_A], total: 1 });
    workplacesMock.mockResolvedValue({ items: [], total: 0 });
    setup({ board: WAITING_BOARD });
    await user.click(await screen.findByRole('button', { name: 'Вызвать следующего' }));
    expect(await screen.findByText(/Нет доступа к этому рабочему месту/)).toBeInTheDocument();
    await waitFor(() =>
      expect(workplacesMock.mock.calls.length).toBeGreaterThanOrEqual(2),
    );
  });

  it('network error: preserves the last rendered server state and offers Retry', async () => {
    const user = userEvent.setup();
    callNextMock.mockRejectedValue(new Error('Network Error'));
    setup({ board: WAITING_BOARD });
    await user.click(await screen.findByRole('button', { name: 'Вызвать следующего' }));
    expect(await screen.findByText(/Ошибка сети/)).toBeInTheDocument();
    // §9: the rendered server state is NOT blanked
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeEnabled();
  });
});

// ---------------------------------------------------------------------------
// §6/§11 the mandatory-reason dialog
// ---------------------------------------------------------------------------

describe('NURSE-V2 N2-5 tablet — incomplete reason UX', () => {
  async function openExecutionDialog() {
    const user = userEvent.setup();
    setup({ board: IN_PROGRESS_BOARD });
    const buttons = await screen.findAllByRole('button', { name: 'Не завершено' });
    await user.click(buttons[0]);
    const textarea = await screen.findByLabelText(/Причина \(обязательно\)/);
    // The Modal kit moves focus on mount via requestAnimationFrame; let it
    // settle and take the focus back BEFORE typing, otherwise the field
    // blurs mid-type and the input is truncated.
    await new Promise((resolve) => setTimeout(resolve, 30));
    await user.click(textarea);
    return { user, textarea };
  }

  it('rejects blank and whitespace-only reasons (button stays disabled)', async () => {
    const { user, textarea } = await openExecutionDialog();
    const submit = screen.getByRole('button', { name: 'Сохранить' });
    expect(submit).toBeDisabled();
    await user.type(textarea, '   ');
    expect(submit).toBeDisabled();
    expect(screen.getByText('Укажите причину')).toBeInTheDocument();
  });

  it('submits a TRIMMED reason and closes the dialog', async () => {
    const { user, textarea } = await openExecutionDialog();
    await user.type(textarea, '  тошнота  ');
    const submit = screen.getByRole('button', { name: 'Сохранить' });
    expect(submit).toBeEnabled();
    await user.click(submit);
    await waitFor(() =>
      expect(incompleteExecutionMock).toHaveBeenCalledWith(55, {
        reason: 'тошнота',
      }),
    );
  });

  it('blocks an over-length reason (200 max)', async () => {
    const { textarea } = await openExecutionDialog();
    // The Modal kit's focus-restore rAF can blur the field mid-type in a
    // full-suite run; the over-length branch is a validation-logic check,
    // so the value is set directly (the trimmed-submit test keeps the
    // real userEvent typing path).
    fireEvent.change(textarea, { target: { value: 'а'.repeat(201) } });
    expect(screen.getByText('Максимум 200 символов')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// §8 reload restore — server state only
// ---------------------------------------------------------------------------

describe('NURSE-V2 N2-5 tablet — reload restore', () => {
  it('restores the held current patient purely from the server state', async () => {
    // no localStorage primed — everything must come from the GETs
    setup({ board: CALLED_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getByText('Вызван')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Начать приём' })).toBeEnabled();
  });

  it('surfaces the drain-recovery card after a mid-flight deactivation', async () => {
    setup({
      board: WAITING_BOARD,
      draining: {
        total: 1,
        items: [
          {
            execution: {
              id: 55,
              visit_service_id: 702,
              queue_entry_id: 11,
              attempt_no: 1,
              status: 'in_progress',
              started_by_user_id: 3,
              started_at: null,
              performed_by_user_id: null,
              completed_at: null,
              incomplete_reason: null,
              created_at: null,
              updated_at: null,
              entry_served: false,
              entry_served_by_user_id: null,
            },
            station: {
              queue_resource_id: 30,
              resource_code: 'proc3',
              resource_display_name: 'Старая станция',
              effective_cabinet: '2',
            },
            entry: { entry_id: 11, number: 17, patient_name: 'Анна Тестова' },
            service: {
              visit_service_id: 702,
              code: 'DRESS01',
              name: 'Перевязка',
              qty: 1,
            },
          },
        ],
      },
    });
    expect(
      await screen.findByText(/Незавершённая работа после смены рабочего места/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Старая станция/)).toBeInTheDocument();
    const completeButtons = screen.getAllByRole('button', { name: 'Выполнено' });
    expect(completeButtons.length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// owner-review round — P1: another nurse's active entry is never "current"
// ---------------------------------------------------------------------------
const OTHER_NURSE_BOARD: NurseStationBoard = {
  ...WAITING_BOARD,
  active: [
    {
      ...WAITING_BOARD.waiting[0],
      id: 42,
      number: 42,
      status: 'called',
      patient_name: 'Ольга Чужая',
      called_by_user_id: 999,
      is_my_claim: false,
      // The owner still holds an ACTIVE assignment — read-only for us.
      claim_owner_assignment_active: true,
      actionable_by_current_user: false,
    },
  ],
  my_entry: null,
};

describe('NURSE-V2 N2-5 tablet — two nurses, one station (owner review P1)', () => {
  it('another nurse\'s active entry NEVER becomes the current patient', async () => {
    setup({ board: OTHER_NURSE_BOARD });
    // my_entry is null -> the idle card with call-next stays available:
    // Nurse B must be able to claim the NEXT waiting patient while
    // Nurse A is serving hers (the §6 two-nurses-one-station contract).
    expect(await screen.findByText('Сейчас у вас никого нет')).toBeInTheDocument();
    const callNext = screen.getByRole('button', { name: 'Вызвать следующего' });
    expect(callNext).toBeEnabled();
    // and no serving actions ever appear for the other nurse's entry
    expect(screen.queryByRole('button', { name: 'Начать приём' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Пациент не явился' })).not.toBeInTheDocument();
  });

  it('the other active entry renders as a read-only overview, not a surface', async () => {
    setup({ board: OTHER_NURSE_BOARD });
    expect(
      await screen.findByText('Обслуживается другим сотрудником'),
    ).toBeInTheDocument();
    expect(screen.getByText('Ольга Чужая')).toBeInTheDocument();
    expect(screen.getByText('№ 42')).toBeInTheDocument();
    expect(screen.getByText('Вызван')).toBeInTheDocument();
    // read-only: no buttons inside the others block
    expect(screen.queryByRole('button', { name: 'Начать приём' })).not.toBeInTheDocument();
  });

  it('my own claim still wins when both nurses hold active entries', async () => {
    const board: NurseStationBoard = {
      ...OTHER_NURSE_BOARD,
      waiting: [],
      counts: { waiting: 0 },
      my_entry: {
        ...WAITING_BOARD.waiting[0],
        id: 11,
        status: 'called',
        is_my_claim: true,
      },
      active: [
        {
          ...WAITING_BOARD.waiting[0],
          id: 11,
          status: 'called',
          is_my_claim: true,
        },
        ...OTHER_NURSE_BOARD.active,
      ],
    };
    setup({ board });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Начать приём' })).toBeEnabled();
    // the other nurse's entry stays in the read-only block
    expect(screen.getByText('Ольга Чужая')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round — P1: access-revocation clears the PHI
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — board-read 403/404 (owner review P1)', () => {
  it('manual refresh on a 403 board: PHI leaves the screen, workplaces re-read', async () => {
    const user = userEvent.setup();
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    boardMock.mockRejectedValue({
      response: { status: 403, data: { detail: 'нет активного назначения' } },
    });
    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    // PHI cleared immediately — the patient may not outlive the revocation
    await waitFor(() => {
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    });
    expect(
      await screen.findByText(/Рабочее место недоступно/),
    ).toBeInTheDocument();
    // the assignment world is re-read (403 = it changed server-side)
    await waitFor(() =>
      expect(workplacesMock.mock.calls.length).toBeGreaterThanOrEqual(2),
    );
  });

  it('focus polling on a 403 board: PHI cleared, workplaces re-read, notice shown', async () => {
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    boardMock.mockRejectedValue({
      response: { status: 403, data: { detail: 'нет активного назначения' } },
    });
    // the 30s silent poll path (throttled focus revalidation stands in)
    fireEvent(window, new Event('focus'));
    await waitFor(() => {
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    });
    expect(
      await screen.findByText(/Нет доступа к этому рабочему месту/),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(workplacesMock.mock.calls.length).toBeGreaterThanOrEqual(2),
    );
  });

  it('manual refresh on a 404 board: the station surface clears, error visible', async () => {
    const user = userEvent.setup();
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    boardMock.mockRejectedValue({
      response: { status: 404, data: { detail: 'очередь не активна' } },
    });
    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    await waitFor(() => {
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    });
    expect(
      await screen.findByText(/Рабочее место недоступно/),
    ).toBeInTheDocument();
  });

  it('network failure on refresh: the stale board STAYS and the error is VISIBLE', async () => {
    const user = userEvent.setup();
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    boardMock.mockRejectedValue(new Error('Network Error'));
    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    // §9 + owner review: keep the rendered server state...
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Повторить' }),
    ).toBeEnabled();
  });
});

// ---------------------------------------------------------------------------
// owner-review round — P1: stale board responses never overwrite a switch
// ---------------------------------------------------------------------------
const BOARD_B: NurseStationBoard = {
  ...WAITING_BOARD,
  queue_resource_id: 20,
  waiting: [
    {
      ...WAITING_BOARD.waiting[0],
      id: 21,
      number: 5,
      patient_name: 'Мария Гонка',
    },
  ],
};

describe('NURSE-V2 N2-5 tablet — workplace switch race (owner review P1)', () => {
  it('a LATE response for workplace A never overwrites workplace B', async () => {
    const user = userEvent.setup();
    setup({ workplaces: [WORKPLACE_A, WORKPLACE_B], board: WAITING_BOARD });
    expect(await screen.findByText('Выберите рабочее место')).toBeInTheDocument();

    let resolveA: (value: NurseStationBoard) => void = () => {};
    boardMock.mockImplementation((id: number) => {
      if (id === 10) {
        return new Promise<NurseStationBoard>((resolve) => {
          resolveA = resolve;
        });
      }
      return Promise.resolve(BOARD_B);
    });

    // select A (slow response), then immediately B (fast response)
    await user.click(screen.getByRole('button', { name: /Процедурный кабинет/ }));
    await user.click(screen.getByRole('button', { name: /Перевязочная/ }));
    expect(await screen.findByText('Мария Гонка')).toBeInTheDocument();

    // A's response finally lands — it must be dropped as stale
    resolveA(WAITING_BOARD);
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    expect(screen.getByText('Мария Гонка')).toBeInTheDocument();
    // the header/selection still say B — no mixed station/patient state
    expect(screen.getByRole('heading', { name: 'Перевязочная' })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round — P2: operation-specific 404 mapping
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — mutation 404 mapping (owner review P2)', () => {
  it('call-next 404 ("no waiting / taken by another"): refetch board, stay ON the station', async () => {
    const user = userEvent.setup();
    callNextMock.mockRejectedValue({
      response: { status: 404, data: { detail: 'Нет ожидающих пациентов' } },
    });
    setup({ board: WAITING_BOARD });
    await user.click(await screen.findByRole('button', { name: 'Вызвать следующего' }));
    // a board refresh happened...
    await waitFor(() => expect(boardMock).toHaveBeenCalledTimes(2));
    // ...but the nurse is NOT ejected: no resetWorkplace, no station-lost error
    expect(
      await screen.findByText(/Состояние уже изменилось/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Рабочее место недоступно/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Нет доступа к этому рабочему месту/)).not.toBeInTheDocument();
    expect(workplacesMock).toHaveBeenCalledTimes(1);
    // the station stays usable — the board is still rendered
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round — P2: a fresh assignment lands without a page reload
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — workplaces discovery (owner review P2)', () => {
  it('manual refresh on the zero-workplace screen picks up a NEW assignment', async () => {
    const user = userEvent.setup();
    setup({ workplaces: [] });
    expect(await screen.findByText('Нет назначенного рабочего места')).toBeInTheDocument();
    // the administrator assigns the workplace while the tablet sits here
    workplacesMock.mockResolvedValue({ items: [WORKPLACE_A], total: 1 });
    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    // ...and it lands WITHOUT a full page reload
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
  });

  it('focus refresh on the zero-workplace screen re-reads workplaces too', async () => {
    setup({ workplaces: [] });
    expect(await screen.findByText('Нет назначенного рабочего места')).toBeInTheDocument();
    workplacesMock.mockResolvedValue({ items: [WORKPLACE_A], total: 1 });
    fireEvent(window, new Event('focus'));
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round 2 — P1: the server-proven D1 handover
// ---------------------------------------------------------------------------
const HANDOVER_CALLED_BOARD: NurseStationBoard = {
  ...WAITING_BOARD,
  waiting: [],
  counts: { waiting: 0 },
  active: [
    {
      ...WAITING_BOARD.waiting[0],
      id: 42,
      number: 42,
      status: 'called',
      patient_name: 'Ольга Передача',
      called_by_user_id: 999,
      is_my_claim: false,
      // The owner's assignment is GONE — the server hands it to us.
      claim_owner_assignment_active: false,
      actionable_by_current_user: true,
    },
  ],
  my_entry: null,
};

const HANDOVER_IN_PROGRESS_BOARD: NurseStationBoard = {
  ...HANDOVER_CALLED_BOARD,
  active: [
    {
      ...HANDOVER_CALLED_BOARD.active[0],
      status: 'in_progress',
      visit_id: 77,
      services: [
        {
          visit_service_id: 701,
          service_id: 9,
          code: 'INJ01',
          name: 'Инъекция',
          qty: 1,
          latest_attempt_no: null,
          latest_attempt_status: null,
          in_progress_execution_id: null,
          pending: true,
        },
      ],
    },
  ],
};

describe('NURSE-V2 N2-5 tablet — the D1 handover (owner review round 2 P1)', () => {
  it('a revoked owner leaves the called entry actionable: banner + [Принять пациента]', async () => {
    const user = userEvent.setup();
    setup({ board: HANDOVER_CALLED_BOARD });
    // The takeover renders as the CURRENT patient — the server said so.
    expect(await screen.findByText('Ольга Передача')).toBeInTheDocument();
    expect(
      screen.getByText(/Сотрудник, вызвавший пациента, недоступен/),
    ).toBeInTheDocument();
    // The explicit takeover action (NOT the plain start label).
    const accept = screen.getByRole('button', { name: 'Принять пациента' });
    expect(accept).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Начать приём' })).not.toBeInTheDocument();
    await user.click(accept);
    await waitFor(() => expect(startMock).toHaveBeenCalledWith(10, 42));
  });

  it('a revoked owner leaves the in_progress entry serviceable: banner + services', async () => {
    setup({ board: HANDOVER_IN_PROGRESS_BOARD });
    expect(await screen.findByText('Ольга Передача')).toBeInTheDocument();
    expect(
      screen.getByText(/Сотрудник, вызвавший пациента, недоступен/),
    ).toBeInTheDocument();
    // The service list renders with its own start action — the D1
    // takeover of an already-started service.
    expect(await screen.findByText('Инъекция')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Начать услугу' })).toBeEnabled();
  });

  it('an actionable foreign entry in the others block carries the takeover action', async () => {
    const user = userEvent.setup();
    // my own claim is current; the orphaned entry waits in the others block.
    const board: NurseStationBoard = {
      ...HANDOVER_CALLED_BOARD,
      my_entry: {
        ...WAITING_BOARD.waiting[0],
        id: 11,
        status: 'called',
        is_my_claim: true,
        claim_owner_assignment_active: true,
        actionable_by_current_user: true,
      },
      active: [
        {
          ...WAITING_BOARD.waiting[0],
          id: 11,
          status: 'called',
          is_my_claim: true,
          claim_owner_assignment_active: true,
          actionable_by_current_user: true,
        },
        ...HANDOVER_CALLED_BOARD.active,
      ],
    };
    setup({ board });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getByText('Ольга Передача')).toBeInTheDocument();
    expect(screen.getByText('Доступна передача обслуживания')).toBeInTheDocument();
    const takeover = screen.getByRole('button', { name: 'Принять пациента' });
    await user.click(takeover);
    await waitFor(() => expect(startMock).toHaveBeenCalledWith(10, 42));
  });

  it('an active owner keeps her entry read-only — no takeover surface', async () => {
    setup({ board: OTHER_NURSE_BOARD });
    expect(await screen.findByText('Ольга Чужая')).toBeInTheDocument();
    expect(
      screen.queryByText('Доступна передача обслуживания'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Принять пациента' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Продолжить обслуживание' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Сотрудник, вызвавший пациента, недоступен/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round 2 — P1: switching stations clears A's board at once
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — station switch PHI boundary (owner review round 2 P1)', () => {
  it('A loaded -> choose B (pending): A\'s patient leaves the screen IMMEDIATELY', async () => {
    const user = userEvent.setup();
    setup({ workplaces: [WORKPLACE_A, WORKPLACE_B], board: WAITING_BOARD });
    expect(await screen.findByText('Выберите рабочее место')).toBeInTheDocument();

    let resolveB: (value: NurseStationBoard) => void = () => {};
    boardMock.mockImplementation((id: number) => {
      if (id === 20) {
        return new Promise<NurseStationBoard>((resolve) => {
          resolveB = resolve;
        });
      }
      return Promise.resolve(WAITING_BOARD);
    });

    await user.click(screen.getByRole('button', { name: /Процедурный кабинет/ }));
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    // The header already says A while its board is rendered.
    expect(screen.getByRole('heading', { name: 'Процедурный кабинет' })).toBeInTheDocument();

    // Switch to B — B's response is PENDING: A's patient must already be gone.
    await user.click(screen.getByRole('button', { name: /Перевязочная/ }));
    expect(screen.getByRole('heading', { name: 'Перевязочная' })).toBeInTheDocument();
    expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    expect(screen.getByText('Загрузка…')).toBeInTheDocument();

    // B lands — its own patient renders.
    resolveB(BOARD_B);
    expect(await screen.findByText('Мария Гонка')).toBeInTheDocument();
  });

  it('A loaded -> choose B (network error): A\'s patient NEVER renders under B\'s header', async () => {
    const user = userEvent.setup();
    setup({ workplaces: [WORKPLACE_A, WORKPLACE_B], board: WAITING_BOARD });
    expect(await screen.findByText('Выберите рабочее место')).toBeInTheDocument();

    boardMock.mockImplementation((id: number) => {
      if (id === 20) {
        return Promise.reject(new Error('Network Error'));
      }
      return Promise.resolve(WAITING_BOARD);
    });

    await user.click(screen.getByRole('button', { name: /Процедурный кабинет/ }));
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Перевязочная/ }));
    // B fails — the error is visible and station A's PHI stays OUT.
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Перевязочная' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeEnabled();
  });
});

// ---------------------------------------------------------------------------
// owner-review round 2 — P1: revocation clears ALL PHI synchronously
// ---------------------------------------------------------------------------
const DRAINING_ITEM = {
  execution: {
    id: 55,
    visit_service_id: 702,
    queue_entry_id: 11,
    attempt_no: 1,
    status: 'in_progress',
    started_by_user_id: 3,
    started_at: null,
    performed_by_user_id: null,
    completed_at: null,
    incomplete_reason: null,
    created_at: null,
    updated_at: null,
    entry_served: false,
    entry_served_by_user_id: null,
  },
  station: {
    queue_resource_id: 30,
    resource_code: 'proc3',
    resource_display_name: 'Старая станция',
    effective_cabinet: '2',
  },
  entry: { entry_id: 11, number: 17, patient_name: 'Анна Тестова' },
  service: { visit_service_id: 702, code: 'DRESS01', name: 'Перевязка', qty: 1 },
};

describe('NURSE-V2 N2-5 tablet — synchronous revocation (owner review round 2 P1)', () => {
  it('mutation 403: board AND draining PHI clear BEFORE the hung workplaces re-read resolves', async () => {
    const user = userEvent.setup();
    setup({
      board: CALLED_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    expect(
      await screen.findByText(/Незавершённая работа после смены рабочего места/),
    ).toBeInTheDocument();

    // The workplaces re-read NEVER resolves — the PHI must still be gone.
    workplacesMock.mockImplementation(
      () => new Promise(() => {
        /* hung forever */
      }),
    );
    // The mutation under test is the START of the called patient.
    startMock.mockRejectedValue({
      response: { status: 403, data: { detail: 'нет активного назначения' } },
    });

    await user.click(screen.getByRole('button', { name: 'Начать приём' }));
    // The regression the owner demanded: PHI out BEFORE the resolution.
    await waitFor(() => {
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    });
    expect(
      screen.queryByText(/Незавершённая работа после смены рабочего места/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Выполнено' }),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText(/Нет доступа к этому рабочему месту/),
    ).toBeInTheDocument();
  });

  it('draining GET 403: the drain card (PHI + terminal actions) clears at once', async () => {
    setup({
      board: WAITING_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(
      await screen.findByText(/Незавершённая работа после смены рабочего места/),
    ).toBeInTheDocument();

    // The revocation is real: the world answers with NO workplaces left.
    workplacesMock.mockResolvedValue({ items: [], total: 0 });
    drainingMock.mockRejectedValue({
      response: { status: 403, data: { detail: 'role revoked' } },
    });
    fireEvent(window, new Event('focus'));

    await waitFor(() => {
      expect(
        screen.queryByText(/Незавершённая работа после смены рабочего места/),
      ).not.toBeInTheDocument();
    });
    // The unified clear also took the board's patient + the selection.
    expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    expect(
      await screen.findByText(/Нет доступа к этому рабочему месту/),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner review round 3 — P1: the final 401 is the SAME revocation boundary
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — 401 dead-session revocation (owner review round 3 P1)', () => {
  it('mutation 401: board AND draining PHI clear BEFORE the hung workplaces re-read resolves', async () => {
    const user = userEvent.setup();
    setup({
      board: CALLED_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    expect(
      await screen.findByText(/Незавершённая работа после смены рабочего места/),
    ).toBeInTheDocument();

    // The dead session's workplaces re-read NEVER resolves — the PHI must
    // still be gone: 401 is fail-closed, never a generic Retry.
    workplacesMock.mockImplementation(
      () => new Promise(() => {
        /* hung forever */
      }),
    );
    // The retry after a failed token refresh answers 401.
    startMock.mockRejectedValue({
      response: { status: 401, data: { detail: 'сессия истекла' } },
    });

    await user.click(screen.getByRole('button', { name: 'Начать приём' }));
    await waitFor(() => {
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    });
    expect(
      screen.queryByText(/Незавершённая работа после смены рабочего места/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Выполнено' }),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText(/Нет доступа к этому рабочему месту/),
    ).toBeInTheDocument();
  });

  it('manual refresh on a 401 board: PHI leaves the screen, workplaces re-read', async () => {
    const user = userEvent.setup();
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    boardMock.mockRejectedValue({
      response: { status: 401, data: { detail: 'сессия истекла' } },
    });
    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    // PHI cleared immediately — a dead session may not keep the board
    // (the synchronous-before-re-read ordering is the mutation 401 pin
    // above: both paths run the SAME resetWorkplace machinery).
    await waitFor(() => {
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    });
    expect(
      await screen.findByText(/Рабочее место недоступно/),
    ).toBeInTheDocument();
    // the access world is re-read (401 = the session that guards it died)
    await waitFor(() =>
      expect(workplacesMock.mock.calls.length).toBeGreaterThanOrEqual(2),
    );
  });

  it('focus polling on a 401 board: PHI cleared, workplaces re-read, notice shown', async () => {
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    boardMock.mockRejectedValue({
      response: { status: 401, data: { detail: 'сессия истекла' } },
    });
    // the 30s silent poll path (throttled focus revalidation stands in)
    fireEvent(window, new Event('focus'));
    await waitFor(() => {
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    });
    expect(
      await screen.findByText(/Нет доступа к этому рабочему месту/),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(workplacesMock.mock.calls.length).toBeGreaterThanOrEqual(2),
    );
  });
});

// ---------------------------------------------------------------------------
// owner review round 3 — P2: the workplaces reader is latest-wins
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — workplaces epoch (owner review round 3 P2)', () => {
  it('a LATE workplaces response never resurrects the revoked station list', async () => {
    const user = userEvent.setup();
    // The initial read (the old world's answer) is SLOW.
    let resolveInitial: (value: { items: NurseWorkplace[]; total: number }) => void =
      () => {};
    workplacesMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveInitial = resolve;
        }),
    );
    setup({ board: WAITING_BOARD });

    // A newer read proves the world empty (assignment revoked) — the
    // zero-workplace screen is the current truth.
    workplacesMock.mockResolvedValue({ items: [], total: 0 });
    await user.click(await screen.findByRole('button', { name: 'Обновить' }));
    expect(
      await screen.findByText('Нет назначенного рабочего места'),
    ).toBeInTheDocument();

    // The OLD world's answer finally lands — it must NOT re-apply its
    // station list (no resurrection of a revoked workflow).
    resolveInitial({ items: [WORKPLACE_A, WORKPLACE_B], total: 2 });
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(
      screen.getByText('Нет назначенного рабочего места'),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Процедурный кабинет/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Перевязочная/ }),
    ).not.toBeInTheDocument();
  });

  it('a LATE workplaces 403 failure never wipes the freshly restored workflow', async () => {
    const user = userEvent.setup();
    // The initial read started under a world that would answer 403 — but
    // its answer is SLOW.
    let rejectInitial: (reason: unknown) => void = () => {};
    workplacesMock.mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectInitial = reject;
        }),
    );
    setup({ board: WAITING_BOARD });

    // A newer read restores the assignment world: one station, its board.
    workplacesMock.mockResolvedValue({ items: [WORKPLACE_A], total: 1 });
    await user.click(await screen.findByRole('button', { name: 'Обновить' }));
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();

    // The STALE failure finally lands — it must NOT run its access-loss
    // clear over the newer, live workflow.
    rejectInitial({
      response: { status: 403, data: { detail: 'нет активного назначения' } },
    });
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
    expect(
      screen.queryByText(/Нет доступа к этому рабочему месту/),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner review round 4 — P2: a superseded resetWorkplace re-read must not
// erase the workflow a newer generation restored
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — stale resetWorkplace (owner review round 4 P2)', () => {
  it('a LATE superseded resetWorkplace re-read never erases the restored workflow', async () => {
    const user = userEvent.setup();
    setup({ board: CALLED_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();

    // The mutation 403 runs resetWorkplace: the PHI clears synchronously,
    // then the dead world's listWorkplaces re-read (R1) HANGS.
    let resolveStale: (value: { items: NurseWorkplace[]; total: number }) => void =
      () => {};
    workplacesMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveStale = resolve;
        }),
    );
    startMock.mockRejectedValue({
      response: { status: 403, data: { detail: 'назначение отозвано' } },
    });
    await user.click(screen.getByRole('button', { name: 'Начать приём' }));
    await waitFor(() => {
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument();
    });
    expect(
      await screen.findByText(/Нет доступа к этому рабочему месту/),
    ).toBeInTheDocument();

    // A NEWER generation re-reads the world while R1 hangs: the lone
    // station re-selects and its fresh board renders.
    workplacesMock.mockResolvedValue({ items: [WORKPLACE_A], total: 1 });
    await user.click(await screen.findByRole('button', { name: 'Обновить' }));
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();

    // R1 finally lands LATE — the epoch already rejected it (superseded).
    // The stale resetWorkplace round must NOT null the restored selection:
    // the pre-fix code mapped the superseded result to [] and ran
    // applySelection(null), wiping the fresh workflow.
    resolveStale({ items: [WORKPLACE_A], total: 1 });
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
    expect(
      screen.queryByText(/Нет назначенного рабочего места/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Нет доступа к этому рабочему месту/),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round 2 — P2: a stale silent-poll FAILURE is discarded
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — stale silent failures (owner review round 2 P2)', () => {
  it('a LATE 403 from a superseded silent poll never blanks the fresh board', async () => {
    const user = userEvent.setup();
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();

    let rejectSilent: (reason: unknown) => void = () => {};
    let silentStarted = false;
    boardMock.mockImplementation((id: number) => {
      if (id === 10 && !silentStarted) {
        silentStarted = true;
        return new Promise((_resolve, reject) => {
          rejectSilent = reject;
        });
      }
      return Promise.resolve(WAITING_BOARD);
    });

    // The silent poll starts (a pending board GET)...
    fireEvent(window, new Event('focus'));
    await waitFor(() => expect(silentStarted).toBe(true));
    // ...then a manual refresh supersedes it and lands a FRESH board.
    await user.click(screen.getByRole('button', { name: 'Обновить' }));
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();

    // The silent poll finally fails with 403 — it must be DISCARDED.
    rejectSilent({ response: { status: 403, data: { detail: 'stale' } } });
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.queryByText(/Нет доступа к этому рабочему месту/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round 2 — P2: workplaces failure is not "no assignments"
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — workplaces failure contract (owner review round 2 P2)', () => {
  it('network failure on refresh: the workflow STAYS, the error is VISIBLE', async () => {
    const user = userEvent.setup();
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();

    workplacesMock.mockRejectedValue(new Error('Network Error'));
    await user.click(screen.getByRole('button', { name: 'Обновить' }));

    expect(
      await screen.findByText(/Не удалось обновить рабочие места/),
    ).toBeInTheDocument();
    // NOT a proven "no assignments" — the current workflow survives.
    expect(screen.queryByText('Нет назначенного рабочего места')).not.toBeInTheDocument();
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Процедурный кабинет' })).toBeInTheDocument();
  });

  it('network failure on the zero-workplace screen: the "none assigned" claim disappears', async () => {
    const user = userEvent.setup();
    setup({ workplaces: [] });
    expect(await screen.findByText('Нет назначенного рабочего места')).toBeInTheDocument();

    workplacesMock.mockRejectedValue(new Error('Network Error'));
    await user.click(screen.getByRole('button', { name: 'Обновить' }));

    expect(
      await screen.findByText(/Не удалось обновить рабочие места/),
    ).toBeInTheDocument();
    expect(screen.queryByText('Нет назначенного рабочего места')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round 2 — P2: a late draining response cannot resurrect
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — draining epoch (owner review round 2 P2)', () => {
  it('a LATE silent draining response never resurrects a completed card', async () => {
    const user = userEvent.setup();
    // The mount read brings the drain item in (setup's default mock).
    setup({
      board: WAITING_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(
      await screen.findByText(/Незавершённая работа после смены рабочего места/),
    ).toBeInTheDocument();

    // Every read AFTER the mount: #1 = the silent refresh GET (pending
    // until we release it), #2+ = empty (the terminal refetch).
    let drainingCalls = 0;
    let resolveStale: (value: unknown) => void = () => {};
    drainingMock.mockImplementation(() => {
      drainingCalls += 1;
      if (drainingCalls === 1) {
        return new Promise((resolve) => {
          resolveStale = resolve;
        });
      }
      return Promise.resolve({ items: [], total: 0 });
    });

    // A silent draining refresh starts (a pending GET)...
    fireEvent(window, new Event('focus'));
    await waitFor(() => expect(drainingCalls).toBeGreaterThanOrEqual(1));

    // ...the nurse completes the execution — the terminal refetch
    // returns the EMPTY list and the card disappears...
    const complete = await screen.findAllByRole('button', { name: 'Выполнено' });
    await user.click(complete[0]);
    await waitFor(() => {
      expect(
        screen.queryByText(/Незавершённая работа после смены рабочего места/),
      ).not.toBeInTheDocument();
    });

    // ...then the stale silent GET finally answers with the OLD item.
    resolveStale({ items: [DRAINING_ITEM], total: 1 });
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(
      screen.queryByText(/Незавершённая работа после смены рабочего места/),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// owner-review round 2 — P1/P2: the draining read error contract
// ---------------------------------------------------------------------------
describe('NURSE-V2 N2-5 tablet — draining read errors (owner review round 2)', () => {
  it('draining 404: the unprovable items drop, no warning banner', async () => {
    setup({
      board: WAITING_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(
      await screen.findByText(/Незавершённая работа после смены рабочего места/),
    ).toBeInTheDocument();

    drainingMock.mockRejectedValue({
      response: { status: 404, data: { detail: 'surface unavailable' } },
    });
    fireEvent(window, new Event('focus'));

    await waitFor(() => {
      expect(
        screen.queryByText(/Незавершённая работа после смены рабочего места/),
      ).not.toBeInTheDocument();
    });
    // 404 is a PROVEN drop — not a stale-state warning.
    expect(screen.queryByText(/данные не обновились/)).not.toBeInTheDocument();
    // The main board is untouched by a draining 404.
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
  });

  it('draining network failure: the stale list STAYS with a visible warning', async () => {
    setup({
      board: WAITING_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(
      await screen.findByText(/Незавершённая работа после смены рабочего места/),
    ).toBeInTheDocument();

    drainingMock.mockRejectedValue(new Error('Network Error'));
    fireEvent(window, new Event('focus'));

    expect(
      await screen.findByText(/Незавершённая работа могла измениться/),
    ).toBeInTheDocument();
    // §9 stale-state contract: the last rendered drain list survives.
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Выполнено' }).length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// owner-review re-review — the dialog subject boundary (P1) + reader
// symmetry (P2) + updater purity (P2) + the routine-switch draining
// discovery (P2)
// ---------------------------------------------------------------------------

describe('NURSE-V2 N2-5 tablet — re-review: dialog subject boundary (P1)', () => {
  it('the draining incomplete-reason dialog OPENS on the zero-workplace screen (§8 drain recovery)', async () => {
    const user = userEvent.setup();
    // THE drain-recovery world: the assignment was deactivated
    // mid-flight — zero workplaces, only the started execution is left.
    setup({
      workplaces: [],
      board: null,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(
      await screen.findByText(/Незавершённая работа после смены рабочего места/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Не завершено' }));
    // The dialog STAYS OPEN — the blanket stationBoard==null close used
    // to kill it the instant it opened on a stationless surface.
    const textarea = await screen.findByLabelText(/Причина \(обязательно\)/);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(textarea).toBeInTheDocument();
    await user.click(textarea);
    await user.type(textarea, 'пациентка ушла');
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() =>
      expect(incompleteExecutionMock).toHaveBeenCalledWith(55, {
        reason: 'пациентка ушла',
      }),
    );
  });

  it('an entry dialog closes when its entry leaves the station board (the original close intent, refined)', async () => {
    const user = userEvent.setup();
    setup({ board: CALLED_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    await user.click(
      screen.getByRole('button', { name: 'Завершить без выполнения' }),
    );
    expect(
      await screen.findByLabelText(/Причина \(обязательно\)/),
    ).toBeInTheDocument();
    // A colleague terminal-served the entry: the fresh board carries no
    // active rows — the dialog's SUBJECT is gone (the board itself stays).
    boardMock.mockResolvedValue(WAITING_BOARD);
    fireEvent(window, new Event('focus'));
    await waitFor(() =>
      expect(
        screen.queryByLabelText(/Причина \(обязательно\)/),
      ).not.toBeInTheDocument(),
    );
  });

  it('an execution dialog STAYS OPEN while its execution renders in the draining card only', async () => {
    const user = userEvent.setup();
    // Station present (waiting) + a draining execution with id 55.
    setup({
      board: WAITING_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Не завершено' }));
    const textarea = await screen.findByLabelText(/Причина \(обязательно\)/);
    await new Promise((resolve) => setTimeout(resolve, 50));
    // The subject renders in the draining card — the dialog survives
    // even though no station service carries execution 55.
    expect(textarea).toBeInTheDocument();
    await user.click(textarea);
    await user.type(textarea, 'реагент закончился');
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() =>
      expect(incompleteExecutionMock).toHaveBeenCalledWith(55, {
        reason: 'реагент закончился',
      }),
    );
  });
});

describe('NURSE-V2 N2-5 tablet — re-review: reader symmetry (P2)', () => {
  it('a successful silent poll CLEARS the stale board error (the honest label cuts both ways)', async () => {
    setup({ board: WAITING_BOARD });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    // The foreground refresh fails on the network: §9 keeps the rendered
    // board and shows the visible error.
    boardMock.mockRejectedValueOnce(new Error('Network Error'));
    fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
    // The silent poll then succeeds: the fresh board lands and the
    // "possibly outdated" banner must NOT outlive the fresh data.
    fireEvent(window, new Event('focus'));
    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument(),
    );
    expect(screen.getByText('Анна Тестова')).toBeInTheDocument();
  });

  it('a 404 board clears the station surface but KEEPS the draining card (§8: role-scoped, station-independent)', async () => {
    setup({
      board: WAITING_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getByText(/Старая станция/)).toBeInTheDocument();
    boardMock.mockRejectedValue({
      response: { status: 404, data: { detail: 'очередь не активна' } },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));
    // The station surface clears...
    await waitFor(() =>
      expect(screen.queryByText('Анна Тестова')).not.toBeInTheDocument(),
    );
    expect(
      await screen.findByText(/Рабочее место недоступно/),
    ).toBeInTheDocument();
    // ...but the nurse's OWN started work (the drain card) SURVIVES the
    // station 404 — the foreground reader now matches the silent one.
    expect(screen.getByText(/Старая станция/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Выполнено' }).length).toBe(1);
  });
});

describe('NURSE-V2 N2-5 tablet — re-review: updater purity (P2)', () => {
  it('submitting the reason dialog fires the terminal mutation EXACTLY ONCE under StrictMode', async () => {
    const user = userEvent.setup();
    workplacesMock.mockResolvedValue({ items: [WORKPLACE_A], total: 1 });
    boardMock.mockResolvedValue(IN_PROGRESS_BOARD);
    drainingMock.mockResolvedValue({ items: [], total: 0 });
    window.localStorage.clear();
    // StrictMode double-invokes state updaters in development — the
    // dispatch must live OUTSIDE the updater or the terminal mutation
    // fires twice.
    renderWithProviders(
      <StrictMode>
        <NurseTabletPage />
      </StrictMode>,
      { routerProps: { initialEntries: ['/nurse'] } },
    );
    const buttons = await screen.findAllByRole('button', {
      name: 'Не завершено',
    });
    await user.click(buttons[0]);
    const textarea = await screen.findByLabelText(/Причина \(обязательно\)/);
    await new Promise((resolve) => setTimeout(resolve, 30));
    await user.click(textarea);
    await user.type(textarea, 'тошнота');
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() =>
      expect(incompleteExecutionMock).toHaveBeenCalledTimes(1),
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(incompleteExecutionMock).toHaveBeenCalledTimes(1);
  });
});

describe('NURSE-V2 N2-5 tablet — re-review: routine station change keeps the draining card (P2)', () => {
  it('the «Сменить» button returns the picker WITHOUT hiding the drain card', async () => {
    const user = userEvent.setup();
    setup({
      workplaces: [WORKPLACE_A, WORKPLACE_B],
      board: WAITING_BOARD,
      draining: { items: [DRAINING_ITEM], total: 1 },
    });
    // The stored preference primes the restored selection (a UI HINT —
    // §4): set AFTER setup (which clears storage) but synchronously,
    // before the initial-load effect's post-await read.
    window.localStorage.setItem('nurse.serving.workplace', '10');
    expect(await screen.findByText('Анна Тестова')).toBeInTheDocument();
    expect(screen.getByText(/Старая станция/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Сменить' }));
    // The picker is back...
    expect(
      await screen.findByRole('button', { name: /Перевязочная/ }),
    ).toBeInTheDocument();
    // ...and the drain card (the nurse's own started work) never left.
    expect(screen.getByText(/Старая станция/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Выполнено' }).length).toBe(1);
  });
});
