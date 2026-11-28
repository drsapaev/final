import type { ComponentProps, ReactNode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DocumentPreview } from '../workspace/DocumentPreview';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/api/client', () => ({ apiClient: { get } }));
vi.mock('@/i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key, language: 'ru' }) }));
vi.mock('../../ui/macos', () => ({
  Button: (props: ComponentProps<'button'>) => <button {...props} />,
  Modal: ({ children, actions }: { children: ReactNode; actions: ReactNode }) => <div>{children}{actions}</div>,
}));

const base = { visitId: 22, status: 'amended', data: {}, dirty: false, onClose: () => {} };

describe('Printing an amended EMR', () => {
  beforeEach(() => get.mockReset());

  it('identifies the amendment immediately and waits for the exact revision', async () => {
    let finish!: (value: { data: { version: number; change_type: string; change_summary: string } }) => void;
    get.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
    const { rerender } = render(<DocumentPreview {...base} version={3} />);
    const print = screen.getByRole('button', { name: 'emr_workspace.print' });
    expect(screen.getByText('misc.visit_emr_status_amended')).toBeVisible();
    expect(print).toBeDisabled();

    await act(async () => finish({ data: { version: 3, change_type: 'amended', change_summary: 'SYNTHETIC correction' } }));
    expect(print).toBeEnabled();
    expect(screen.getByText('SYNTHETIC correction')).toBeInTheDocument();

    get.mockResolvedValueOnce({ data: { version: 3, change_type: 'amended', change_summary: 'SYNTHETIC stale' } });
    rerender(<DocumentPreview {...base} version={4} />);
    await screen.findByRole('alert');
    expect(print).toBeDisabled();
    expect(screen.queryByText('SYNTHETIC correction')).toBeNull();
    expect(screen.queryByText('SYNTHETIC stale')).toBeNull();

    get.mockResolvedValueOnce({ data: { version: 4, change_type: 'amended', change_summary: 'SYNTHETIC current' } });
    fireEvent.click(screen.getByRole('button', { name: 'emr_workspace.retry' }));
    await waitFor(() => expect(print).toBeEnabled());
    expect(screen.getByText('SYNTHETIC current')).toBeInTheDocument();
  });

  it('can print a signed version directly', () => {
    render(<DocumentPreview {...base} status="signed" version={2} />);
    expect(screen.getByRole('button', { name: 'emr_workspace.print' })).toBeEnabled();
    expect(get).not.toHaveBeenCalled();
  });
});
