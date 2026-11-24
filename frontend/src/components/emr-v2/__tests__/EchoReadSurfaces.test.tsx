import type { ComponentProps, ReactNode } from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { EMRWorkspaceData } from '@/api/emrWorkspace';
import { CardiologySection } from '../sections/specialty/CardiologySection';
import { DocumentPreview } from '../workspace/DocumentPreview';
import { WorkspaceSidePanel } from '../workspace/VisitHistory';

vi.mock('@/hooks/useLabReporting', () => ({ useLabReporting: () => ({}) }));
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

    expect(screen.getByText(/echo_tte_reporting · .*61\.25 % · .*biplane_simpson_2d · 2026-11-20/)).toBeVisible();
    expect(screen.getByText(/echo_legacy_measurements · EF 54%, SYNTHETIC legacy method · 2026-09-04/)).toBeVisible();
    expect(screen.queryByText(/61\.25.*54/)).toBeNull();
  });
});
