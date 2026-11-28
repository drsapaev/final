import type { ComponentProps } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FollowUpEditor } from '../VisitHistory';

vi.mock('@/hooks/useLabReporting', () => ({ useLabReporting: () => ({}) }));
vi.mock('@/api/emrWorkspace', () => ({
  getEMRWorkspace: vi.fn(),
  getWorkspaceHistoryDocument: vi.fn(),
}));
vi.mock('@/i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string) => ({
      'emr_workspace.visit_type': 'Visit type',
      'emr_workspace.initial_visit': 'Initial',
      'emr_workspace.repeat_visit': 'Follow-up',
      'emr_workspace.new_complaint_toggle': 'New complaint',
      'emr_workspace.unselected': 'Unselected',
    }[key] ?? key),
  }),
}));
vi.mock('../../../ui/macos', () => ({
  Button: ({ size: _size, variant: _variant, ...props }: ComponentProps<'button'> & { size?: string; variant?: string }) => <button {...props} />,
  Input: (props: ComponentProps<'input'>) => <input {...props} />,
  Textarea: (props: ComponentProps<'textarea'>) => <textarea {...props} />,
}));
vi.mock('../AdultTteSummary', () => ({ AdultTteSummary: () => null }));
vi.mock('../ClinicalSummary', () => ({ ClinicalSummary: () => null }));
vi.mock('../DocumentPreview', () => ({ DocumentPreview: () => null }));
vi.mock('../LabTrendPanel', () => ({ LabTrendPanel: () => null }));

describe('FollowUpEditor visit type controls', () => {
  it('keeps initial, follow-up and new-complaint modes distinct', () => {
    const onChange = vi.fn();
    const value = {
      mode: null,
      changes: '',
      actual_treatment: '',
      prior_plan_follow_through: '',
      new_results: '',
      transferred_fields: [],
    };

    const { rerender } = render(<FollowUpEditor value={value} disabled={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Initial' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...value, mode: 'initial' });

    fireEvent.click(screen.getByRole('button', { name: 'Follow-up' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...value, mode: 'follow_up' });

    rerender(<FollowUpEditor value={{ ...value, mode: 'follow_up' }} disabled={false} onChange={onChange} />);
    const newComplaint = screen.getByRole('checkbox', { name: 'New complaint' });
    fireEvent.click(newComplaint);
    expect(onChange).toHaveBeenLastCalledWith({ ...value, mode: 'new_complaint' });

    rerender(<FollowUpEditor value={{ ...value, mode: 'new_complaint' }} disabled={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'New complaint' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...value, mode: 'follow_up' });
  });
});
