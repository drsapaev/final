/**
 * DERMSCHED-FE-004 (owner registry #4063; review-group audit comment
 * 6690288950) — the 2-second success timer can dismiss a newly reopened
 * schedule-next dialog.
 *
 * After a successful scheduling the modal starts an untracked
 * `setTimeout(() => { onClose?.(); resetForm(); }, 2000)`. There is no
 * timeout cancellation on unmount or on a new-open generation, and the
 * parent controls `isOpen` on a persistently mounted component — so the
 * stale session-A timer fires while dialog B is open and closes it while
 * B's form is in progress.
 *
 * Contract after the repair: the timer handle is tracked and cancelled on
 * every open-state transition (manual close, fresh open for the next
 * patient) and on unmount — a stale timer never closes a dialog
 * generation it does not belong to; the fresh dialog's form stays intact;
 * the success auto-close for a dialog that is left untouched still works.
 *
 * Red-first: on the pre-fix source the stale-timer cases fail (the
 * reopened dialog is closed and its preselected patient wiped) while the
 * positive auto-close control passes on both.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ScheduleNextModal from '../ScheduleNextModal';
import { api } from '../../../api/client';

vi.mock('../../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn(() => 'synthetic-doctor-token') },
}));
vi.mock('../../../utils/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);

function jsonResponse(data: unknown, status = 200) {
  return { data, status } as never;
}

const PATIENTS = [
  { id: 9, first_name: 'Ann', last_name: 'Ayn', phone: '100' },
  { id: 22, first_name: 'Cy', last_name: 'Doe', phone: '220' },
];
const SERVICES = [{ id: 5, name: 'Derma service', category: 'derma', code: 'D1', price: 100 }];

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockedGet.mockImplementation(async (url: unknown) => {
    const path = String(url);
    if (path === '/patients') return jsonResponse(PATIENTS);
    if (path === '/services') return jsonResponse(SERVICES);
    throw new Error(`unexpected GET ${path}`);
  });
  mockedPost.mockResolvedValue(jsonResponse({
    visit_id: 55,
    confirmation: { channel: 'telegram', token: 'tok-1' },
  }));
});

afterEach(() => {
  vi.useRealTimers();
});

async function submit(container: HTMLElement, patientId: string) {
  await waitFor(() => expect(mockedGet).toHaveBeenCalledWith('/services'));
  expect((screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement).value).toBe(patientId);
  fireEvent.change(screen.getByLabelText('Schedule next visit date'), { target: { value: '2030-01-01' } });
  fireEvent.change(screen.getByLabelText('Schedule next visit service 1'), { target: { value: '5' } });
  fireEvent.submit(container.querySelector('form') as HTMLFormElement);
}

async function submitSuccessfully(container: HTMLElement, patientId: string) {
  await submit(container, patientId);
  await waitFor(() => expect(mockedPost).toHaveBeenCalledTimes(1));
}

async function selectPatient(patientId: string) {
  const select = screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement;
  await waitFor(() => expect(Array.from(select.options).some((option) => option.value === patientId)).toBe(true));
  fireEvent.change(select, { target: { value: patientId } });
  return select;
}

function deferredResponse() {
  let resolve!: (response: ReturnType<typeof jsonResponse>) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<ReturnType<typeof jsonResponse>>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  mockedPost.mockReturnValueOnce(promise);
  return { resolve, reject };
}

describe('DERMSCHED-FE-004 — a stale success timer never closes a dialog generation it does not belong to', () => {
  it('success A → manual close → reopen for B: the stale A timer leaves B open and intact', async () => {
    const onClose = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9, first_name: 'Ann' }} onClose={onClose} />);
    await submitSuccessfully(view.container, '9');

    // Manual close + immediate reopen for patient B (persistently mounted
    // `isOpen` prop — no unmount happens between the two sessions).
    view.rerender(<ScheduleNextModal isOpen={false} patient={{ id: 9, first_name: 'Ann' }} onClose={onClose} />);
    view.rerender(<ScheduleNextModal isOpen patient={{ id: 22, first_name: 'Cy' }} onClose={onClose} />);
    expect((screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement).value).toBe('22');

    // Past the 2s window the stale A timer must be dead: B stays open and
    // B's preselection is intact.
    act(() => { vi.advanceTimersByTime(2200); });
    expect(onClose).not.toHaveBeenCalled();
    expect((screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement).value).toBe('22');
  });

  it('success A → unmount: the pending timer never fires after unmount', async () => {
    const onClose = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9, first_name: 'Ann' }} onClose={onClose} />);
    await submitSuccessfully(view.container, '9');

    view.unmount();
    act(() => { vi.advanceTimersByTime(2200); });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('positive control: the untouched dialog still auto-closes through the success timer', async () => {
    const onClose = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9, first_name: 'Ann' }} onClose={onClose} />);
    await submitSuccessfully(view.container, '9');

    // No open-state transition, no unmount — the auto-close must fire.
    act(() => { vi.advanceTimersByTime(2200); });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});


describe('schedule-next submission belongs to its originating dialog session', () => {
  it('keeps B saving and open when the earlier save for A succeeds', async () => {
    const a = deferredResponse();
    const b = deferredResponse();
    const onSuccess = vi.fn();
    const onClose = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9 }} onSuccess={onSuccess} onClose={onClose} />);
    await submit(view.container, '9');

    view.rerender(<ScheduleNextModal isOpen={false} />);
    view.rerender(<ScheduleNextModal isOpen patient={{ id: 22 }} onSuccess={onSuccess} onClose={onClose} />);
    await submit(view.container, '22');
    expect(mockedPost).toHaveBeenCalledTimes(2);
    const save = view.container.querySelector<HTMLButtonElement>('button[type="submit"]')!;

    await act(async () => { a.resolve(jsonResponse({ visit_id: 55 })); });
    expect(onSuccess).toHaveBeenCalledExactlyOnceWith({ visit_id: 55 }, expect.objectContaining({ patient_id: 9 }));
    expect(save.disabled).toBe(true);
    expect(screen.queryByText('misc.snm_visit_scheduled')).toBeNull();
    act(() => { vi.advanceTimersByTime(2200); });
    expect(onClose).not.toHaveBeenCalled();
    expect((screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement).value).toBe('22');

    await act(async () => { b.resolve(jsonResponse({ visit_id: 56 })); });
    expect(onSuccess).toHaveBeenLastCalledWith({ visit_id: 56 }, expect.objectContaining({ patient_id: 22 }));
    expect(onSuccess).toHaveBeenCalledTimes(2);
    expect(save.disabled).toBe(true);
    act(() => { vi.advanceTimersByTime(2200); });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('keeps the selected patient saving when a prior selection completes', async () => {
    const a = deferredResponse();
    const b = deferredResponse();
    const onSuccess = vi.fn();
    const onClose = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9 }} onSuccess={onSuccess} onClose={onClose} />);
    await submit(view.container, '9');

    const picker = await selectPatient('22');
    await submit(view.container, '22');
    expect(mockedPost).toHaveBeenCalledTimes(2);

    await act(async () => { a.resolve(jsonResponse({ visit_id: 55 })); });
    expect(onSuccess).toHaveBeenCalledExactlyOnceWith({ visit_id: 55 }, expect.objectContaining({ patient_id: 9 }));
    expect(view.container.querySelector<HTMLButtonElement>('button[type="submit"]')!.disabled).toBe(true);
    expect(screen.queryByText('misc.snm_visit_scheduled')).toBeNull();

    act(() => { vi.advanceTimersByTime(2200); });
    expect(onClose).not.toHaveBeenCalled();
    expect(picker.value).toBe('22');
    await act(async () => { b.resolve(jsonResponse({ visit_id: 56 })); });
    expect(onSuccess).toHaveBeenLastCalledWith({ visit_id: 56 }, expect.objectContaining({ patient_id: 22 }));
  });

  it('cancels the completed selection auto-close when the picker changes patient', async () => {
    const onClose = vi.fn();
    const onSuccess = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9 }} onClose={onClose} onSuccess={onSuccess} />);

    await submitSuccessfully(view.container, '9');
    await waitFor(() => expect(screen.getByText('misc.snm_visit_scheduled')).toBeTruthy());

    const picker = await selectPatient('22');
    act(() => { vi.advanceTimersByTime(2200); });

    expect(onClose).not.toHaveBeenCalled();
    expect(picker.value).toBe('22');
    expect(screen.queryByText('misc.snm_visit_scheduled')).toBeNull();
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });

  it('reuses the uncertain key after booking for another patient', async () => {
    const uncertain = deferredResponse();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9 }} />);
    await submit(view.container, '9');
    const originalKey = mockedPost.mock.calls[0]?.[2]?.headers?.['Idempotency-Key'];
    expect(originalKey).toEqual(expect.any(String));
    await act(async () => {
      uncertain.reject({ response: { status: 503, data: { detail: 'Try again' } } });
    });

    await selectPatient('22');
    await submit(view.container, '22');
    const otherKey = mockedPost.mock.calls[1]?.[2]?.headers?.['Idempotency-Key'];
    expect(otherKey).toEqual(expect.any(String));
    expect(otherKey).not.toBe(originalKey);

    await selectPatient('9');
    fireEvent.change(screen.getByLabelText('Schedule next visit date'), { target: { value: '2030-01-02' } });
    fireEvent.submit(view.container.querySelector('form') as HTMLFormElement);
    expect(mockedPost).toHaveBeenCalledTimes(2);
    expect(screen.getByText('misc.aw_cart_retry_payload_changed')).toBeTruthy();

    await submit(view.container, '9');
    expect(mockedPost).toHaveBeenCalledTimes(3);
    expect(mockedPost.mock.calls[2]?.[2]?.headers?.['Idempotency-Key']).toBe(originalKey);
  });

  it('keeps one save in flight when returning to the same patient', async () => {
    const original = deferredResponse();
    const onSuccess = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9 }} onSuccess={onSuccess} />);
    await submit(view.container, '9');
    await selectPatient('22');
    await selectPatient('9');
    await submit(view.container, '9');
    expect(mockedPost).toHaveBeenCalledTimes(1);

    await act(async () => { original.resolve(jsonResponse({ visit_id: 55 })); });
    expect(onSuccess).toHaveBeenCalledExactlyOnceWith({ visit_id: 55 }, expect.objectContaining({ patient_id: 9 }));
    expect(screen.queryByText('misc.snm_visit_scheduled')).toBeNull();
  });

  it('does not show a stale error when the host replaces the patient without closing', async () => {
    const a = deferredResponse();
    const onSuccess = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 99, patient_id: 9 }} onSuccess={onSuccess} />);
    await submit(view.container, '9');

    view.rerender(<ScheduleNextModal isOpen patient={{ id: 99, patient_id: 22 }} onSuccess={onSuccess} />);
    await act(async () => { a.reject({ response: { data: { detail: 'synthetic A-only error' } } }); });
    expect(screen.queryByText('synthetic A-only error')).toBeNull();
    expect(onSuccess).not.toHaveBeenCalled();
    expect((screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement).value).toBe('22');
  });

  it('keeps the current session when a new patient object has the same canonical ID', async () => {
    const request = deferredResponse();
    const onClose = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 99, patient_id: 9 }} onClose={onClose} />);
    await submit(view.container, '9');

    view.rerender(<ScheduleNextModal isOpen patient={{ id: 100, patient_id: '9' }} onClose={onClose} />);
    await act(async () => { request.resolve(jsonResponse({ visit_id: 55 })); });
    expect(screen.getByText('misc.snm_visit_scheduled')).toBeTruthy();
    act(() => { vi.advanceTimersByTime(2200); });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('notifies the host of the saved visit but does not auto-close after unmount', async () => {
    const request = deferredResponse();
    const onSuccess = vi.fn();
    const onClose = vi.fn();
    const view = render(<ScheduleNextModal isOpen patient={{ id: 9 }} onSuccess={onSuccess} onClose={onClose} />);
    await submit(view.container, '9');
    view.unmount();

    await act(async () => { request.resolve(jsonResponse({ visit_id: 55 })); });
    expect(onSuccess).toHaveBeenCalledExactlyOnceWith({ visit_id: 55 }, expect.objectContaining({ patient_id: 9 }));
    act(() => { vi.advanceTimersByTime(2200); });
    expect(onClose).not.toHaveBeenCalled();
  });
});
