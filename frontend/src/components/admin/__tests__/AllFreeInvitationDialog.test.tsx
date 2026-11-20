import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '../../../api/client';
import AllFreeInvitationDialog, { type InvitationReview } from '../AllFreeInvitationDialog';

vi.mock('../../../api/client', () => ({ api: { post: vi.fn() } }));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ language: 'en', t: (key: string) => key }),
}));
vi.mock('../../ui/macos', () => ({
  Modal: ({ title, children, actions }: { title: string; children: ReactNode; actions: ReactNode }) => (
    <section role="dialog" aria-label={title}>{children}{actions}</section>
  ),
  Button: (props: ButtonHTMLAttributes<HTMLButtonElement>) => <button {...props} />,
}));

const review: InvitationReview = {
  visit_id: 42, patient_id: 3, owner_generation: 4, context_epoch: 5,
  patient_name: 'SYNTHETIC', visit_date: '2030-01-01', visit_time: null,
  channel: 'telegram', currency: 'USD', total_amount: 21.5, token: 'SYNTHETIC-signed-review',
  services: [{ name: 'SYNTHETIC service', code: null, quantity: 2, price: 10.75, total: 21.5 }],
};

describe('All Free invitation task', () => {
  beforeEach(() => vi.mocked(api.post).mockReset());

  it('renders the server review and stages only the explicit protected inbox action', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { state: 'pending' } });
    render(<AllFreeInvitationDialog review={review} onClose={vi.fn()} />);
    expect(screen.getByRole('dialog').textContent).toContain('21.50 USD');
    expect(screen.getByRole('dialog').textContent).not.toContain(review.token);
    expect(api.post).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'admin2.af_invitation_submit' }));

    expect((await screen.findByRole('status')).textContent).toBe('admin2.af_invitation_queued');
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.post).toHaveBeenCalledWith('/visits/42/confirmation-reissue', {
      expected_patient_id: 3, expected_owner_generation: 4, expected_context_epoch: 5,
      channel: 'phone', token: review.token,
    }, { headers: { 'Idempotency-Key': expect.stringMatching(/^[0-9a-f-]{36}$/) } });
    expect(screen.queryByRole('button', { name: 'admin2.af_invitation_submit' })).toBeNull();
  });

  it('retries an uncertain response with the original key and signed context', async () => {
    vi.mocked(api.post)
      .mockRejectedValueOnce(new Error('SYNTHETIC lost response'))
      .mockResolvedValueOnce({ data: { state: 'unknown' } });
    render(<AllFreeInvitationDialog review={review} onClose={vi.fn()} />);
    const submit = () => fireEvent.click(screen.getByRole('button', { name: 'admin2.af_invitation_submit' }));

    submit();
    expect((await screen.findByRole('alert')).textContent).toBe('admin2.af_invitation_error');
    submit();

    expect((await screen.findByRole('status')).textContent).toBe('admin2.af_invitation_unverified');
    const calls = vi.mocked(api.post).mock.calls;
    expect(calls).toHaveLength(2);
    expect(calls[1]).toEqual(calls[0]);
  });
});
