import type { ComponentProps, ReactNode } from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { getWorkspaceHistoryDocument, type EMRWorkspaceData } from '@/api/emrWorkspace';
import { CardiologySection } from '../sections/specialty/CardiologySection';
import { DocumentPreview } from '../workspace/DocumentPreview';
import { WorkspaceSidePanel } from '../workspace/VisitHistory';

vi.mock('@/hooks/useLabReporting', () => ({ useLabReporting: () => ({}) }));
vi.mock('@/api/emrWorkspace', () => ({
  getEMRWorkspace: vi.fn(), getWorkspaceHistoryDocument: vi.fn(),
}));
vi.mock('@/i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'en',
    t: (key: string, options?: Record<string, unknown>) => {
      if (key === 'misc.cs_unit_mm') return 'mm';
      if (key === 'emr_workspace.ef_value') return `EF ${options?.value}%, ${options?.method}`;
      return key;
    },
  }),
}));
vi.mock('../../ui/macos', () => ({
  Button: ({ size: _size, ...props }: Omit<ComponentProps<'button'>, 'size'> & { size?: string }) => <button {...props} />,
  Input: (props: ComponentProps<'input'>) => <input {...props} />,
  Modal: ({ children, actions }: { children: ReactNode; actions: ReactNode }) => <div>{children}{actions}</div>,
}));

const legacyEcho = {
  leftVentricle: { edd: '50', ef: '54' },
  measurement_metadata: { ef_method: 'SYNTHETIC legacy method', measured_at: '2026-09-04' },
};

const structuredEcho = {
  adult_tte: {
    version: 2,
    measurements: {
      lvef: { value: 61.25, unit: '%' },
      lvedd: { value: 5.2, unit: 'cm' },
      lavi: { value: 34, unit: 'mL/m²' },
      tapse: { value: 26, unit: 'mm' },
    },
    ef_method: 'biplane_simpson_2d', measured_at: '2026-11-20', source_visit_id: 99,
  },
};

describe('Adult TTE clinical read surfaces', () => {
  it('shows modern values and legacy diameters separately in the read-only cardiology summary', () => {
    render(<CardiologySection disabled echoData={{ ...legacyEcho, ...structuredEcho, conclusion: 'SYNTHETIC conclusion' }} />);
    fireEvent.click(screen.getByRole('button', { name: 'misc.cs_tab_echo' }));

    const adult = within(screen.getByRole('region', { name: 'emr_workspace.echo_tte_reporting' }));
    expect(adult.getByText(/echo_tte_lvedd 5\.2 cm/)).toBeVisible();
    expect(adult.getByText(/echo_tte_lavi 34 mL\/m²/)).toBeVisible();
    expect(adult.queryByText(/echo_tte_tapse/)).toBeNull();
    expect(screen.getByText('emr_workspace.echo_legacy_measurements')).toBeVisible();
    expect(screen.getByText(/50 mm/)).toBeVisible();
    expect(screen.getByText('SYNTHETIC conclusion')).toBeVisible();
  });

  it('includes the definition, date and measurement method in printable signed records', () => {
    const { rerender } = render(<DocumentPreview visitId={99} status="signed" version={2}
      data={{ specialty_data: { echo: structuredEcho } }} dirty={false} onClose={vi.fn()} />);

    const adult = within(screen.getByRole('region', { name: 'emr_workspace.echo_tte_reporting' }));
    expect(adult.getByText(/echo_tte_lvef 61\.25 % · emr_workspace\.echo_method_biplane_simpson_2d/)).toBeVisible();
    expect(adult.getByText('2026-11-20')).toHaveAttribute('datetime', '2026-11-20');
    expect(adult.queryByText(/echo_tte_lvesd/)).toBeNull();
    expect(screen.queryByText('emr_workspace.echo_legacy_measurements')).toBeNull();

    rerender(<DocumentPreview visitId={98} status="signed" version={1}
      data={{ specialty_data: { echo: legacyEcho } }} dirty={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('region', { name: 'emr_workspace.echo_tte_reporting' })).toBeNull();
    expect(screen.getByText(/echo_edd 50 mm/)).toBeVisible();
  });

  it('keeps the previous and current EF observations separate in the visit timeline', () => {
    const workspace: EMRWorkspaceData = {
      patient: { id: 1, full_name: 'SYNTHETIC patient', birth_date: null, legacy_allergies: null, legacy_conditions: null },
      visit: { id: 99, date: '2026-11-20', status: 'open' },
      clinical_entries: [], allergy_state: 'not_checked', has_more_history: false,
      history: [{
        id: 101, visit_id: 98, version: 1, status: 'signed', visit_date: '2026-09-05', signed_at: null,
        complaints: '', diagnosis: '', treatment: '', recommendations: '',
        vitals: {}, echo: legacyEcho, laboratory: [],
      }],
    };
    render(<WorkspaceSidePanel status="ready" workspace={workspace} currentEcho={structuredEcho}
      readOnly reload={vi.fn()} followUp={{}} onFollowUpChange={vi.fn()} />);
    fireEvent.click(screen.getByText('emr_workspace.measurement_history'));

    const adult = within(screen.getByRole('region', { name: 'emr_workspace.echo_tte_reporting' }));
    expect(adult.getByText(/echo_tte_lvef 61\.25 % · .*biplane_simpson_2d/)).toBeVisible();
    expect(adult.getByText('2026-11-20')).toHaveAttribute('datetime', '2026-11-20');
    expect(screen.getByText(/echo_legacy_measurements · EF 54%, SYNTHETIC legacy method · 2026-09-04/)).toBeVisible();
    expect(screen.queryByText(/61\.25.*54/)).toBeNull();
  });

  it('keeps adult TTE studies without EF visible in the timeline and exact history version', async () => {
    const study = (visitId: number, measuredAt: string, value: number) => ({ adult_tte: {
      version: 2, measurements: { lavi: { value, unit: 'mL/m²' } },
      measured_at: measuredAt, source_visit_id: visitId,
    } });
    const currentEcho = study(99, '2026-11-19', 40);
    const history = {
      id: 101, visit_id: 98, version: 3, visit_date: '2026-09-05', signed_at: null,
      status: 'signed', complaints: '', diagnosis: '', treatment: '', recommendations: '',
      vitals: {}, echo: study(98, '2026-09-04', 35), laboratory: [],
    };
    const workspace: EMRWorkspaceData = {
      patient: { id: 1, full_name: 'SYNTHETIC patient', birth_date: null, legacy_allergies: null, legacy_conditions: null },
      visit: { id: 99, date: '2026-11-20', status: 'open' },
      clinical_entries: [], allergy_state: 'not_checked', has_more_history: false, history: [history],
    };
    const previousEcho = study(98, '2026-09-03', 31);
    vi.mocked(getWorkspaceHistoryDocument)
      .mockResolvedValueOnce({ ...history, data: { specialty_data: { echo: history.echo } } })
      .mockResolvedValueOnce({
        ...history, version: 2, echo: previousEcho, data: { specialty_data: { echo: previousEcho } },
      });
    render(<WorkspaceSidePanel status="ready" workspace={workspace} currentEcho={currentEcho}
      readOnly reload={vi.fn()} followUp={{}} onFollowUpChange={vi.fn()} />);
    fireEvent.click(screen.getByText('emr_workspace.measurement_history'));

    const observations = screen.getAllByRole('region', { name: 'emr_workspace.echo_tte_reporting' });
    expect(observations).toHaveLength(2);
    expect(within(observations[0]!).getByText(/echo_tte_lavi 40 mL\/m²/)).toBeVisible();
    expect(within(observations[0]!).getByText('2026-11-19')).toBeVisible();
    expect(within(observations[1]!).getByText(/echo_tte_lavi 35 mL\/m²/)).toBeVisible();
    expect(within(observations[1]!).getByText('2026-09-04')).toBeVisible();

    const visitDetails = screen.getByText('emr_workspace.history_details').closest('details')!;
    const measurements = screen.getByText('emr_workspace.measurement_history').closest('details')!;
    expect(visitDetails.open).toBe(false);
    fireEvent.click(within(measurements).getByRole('button', { name: '2026-09-05', exact: true }));
    expect(visitDetails.open).toBe(true);

    const details = within(visitDetails);
    expect(await details.findByText(/echo_tte_lavi 35 mL\/m²/)).toBeVisible();
    const version = details.getByRole('spinbutton', { name: 'emr_workspace.document_version' });
    fireEvent.change(version, { target: { value: '2' } });
    fireEvent.click(details.getByRole('button', { name: 'emr_workspace.open_version' }));
    expect(await details.findByText(/echo_tte_lavi 31 mL\/m²/)).toBeVisible();
    expect(details.getByText('2026-09-03')).toBeVisible();
    expect(vi.mocked(getWorkspaceHistoryDocument).mock.lastCall).toEqual([99, 1, 98, 2]);
  });
});
