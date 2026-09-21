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
