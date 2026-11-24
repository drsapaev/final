import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '../../../../api/client';
import RegistrarInvitationTask from '../RegistrarInvitationTask';

vi.mock('../../../../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ language: 'en', t: (key: string) => key }),
}));
vi.mock('../../../../components/ui/macos', () => ({
  Modal: ({ title, children, actions }: { title: string; children: ReactNode; actions: ReactNode }) => (
    <section role="dialog" aria-label={title}>{children}{actions}</section>
  ),
  Button: (props: ButtonHTMLAttributes<HTMLButtonElement>) => <button {...props} />,
}));

const handle = '00000000-0000-4000-8000-000000000042';
const task = {
  visit_id: 42, patient_name: 'SYNTHETIC PATIENT', patient_phone: null,
  visit_date: '2030-01-02', visit_time: '10:45',
};

function Search() {
  return <output data-testid="query">{useLocation().search}</output>;
}

const open = (query: string) => render(
  <MemoryRouter initialEntries={[`/registrar${query}`]}>
    <RegistrarInvitationTask />
    <Search />
  </MemoryRouter>,
);

describe('Registrar invitation from the protected inbox', () => {
  beforeEach(() => vi.mocked(api.get).mockReset());

  it('leaves normal navigation free of task requests', () => {
    open('?dept=cardio');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(api.get).not.toHaveBeenCalled();
  });

  it('reads the canonical task and clears just its handle on close', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: task });
    open(`?invitation=${handle}&dept=cardio`);
    expect(await screen.findByText(task.patient_name)).toBeDefined();
    expect(screen.getByRole('dialog').textContent).toContain(task.visit_time);
    expect(api.get).toHaveBeenCalledTimes(1);
    expect(api.get).toHaveBeenCalledWith(`/notifications/visit-invitation-tasks/${handle}`, {
      signal: expect.any(AbortSignal),
    });

    fireEvent.click(screen.getByRole('button', { name: 'common.close' }));
    expect(screen.getByTestId('query').textContent).toBe('?dept=cardio');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('rejects ambiguous links before sending a request', () => {
    open(`?invitation=${handle}&invitation=${handle}`);
    expect(screen.getByRole('alert').textContent).toBe('registrarPanel.invitation_task_unavailable');
    expect(api.get).not.toHaveBeenCalled();
  });

  it('shows a missing or unauthorized task without contact data or retry', async () => {
    vi.mocked(api.get).mockRejectedValueOnce({ response: { status: 404, data: task } });
    open(`?invitation=${handle}`);

    expect((await screen.findByRole('alert')).textContent).toBe('registrarPanel.invitation_task_unavailable');
    expect(screen.queryByText(task.patient_name)).toBeNull();
    expect(screen.queryByRole('button', { name: 'common.refresh' })).toBeNull();
  });

  it('lets the registrar retry a transient read failure', async () => {
    vi.mocked(api.get).mockRejectedValueOnce({ response: { status: 503 } }).mockResolvedValueOnce({ data: task });
    open(`?invitation=${handle}`);
    expect((await screen.findByRole('alert')).textContent).toBe('registrarPanel.invitation_task_load_error');

    fireEvent.click(screen.getByRole('button', { name: 'common.refresh' }));
    expect(await screen.findByText(task.patient_name)).toBeDefined();
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it('cancels an in-flight read when the invitation is dismissed', () => {
    vi.mocked(api.get).mockReturnValueOnce(new Promise(() => {}));
    open(`?invitation=${handle}`);
    const signal = vi.mocked(api.get).mock.calls[0][1]?.signal;
    expect(signal?.aborted).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'common.close' }));
    expect(signal?.aborted).toBe(true);
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
