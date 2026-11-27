import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '../../../contexts/ThemeContext';
import LabClinicalConfigurationPanel from '../LabClinicalConfigurationPanel';

const mocks = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
  user: null as null | { id: number; role: string; is_active?: boolean },
}));

vi.mock('../../../api/client', () => ({ api: mocks.api, default: mocks.api }));
vi.mock('../../../contexts/AppDataContext', () => ({
  useAppData: () => ({ currentUser: mocks.user }),
}));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const pendingVersion = {
  id: 21,
  version_no: 4,
  status: 'PENDING_APPROVAL' as const,
  configuration_snapshot: {
    method_instructions: [{ method_code: 'SYNTHETIC-METHOD' }],
  },
  primary_lab_physician_user_id: 7,
  substitute_lab_physician_user_id: 8,
  approved_by_user_id: null,
  approved_role_code: null,
  approval_authority_snapshot: null,
  approved_at: null,
  created_at: '2026-11-27T00:00:00Z',
};

const pendingAnalyzerMapping = {
  version_id: 51,
  profile_id: 31,
  version_no: 2,
  equipment_id: 11,
  equipment_name: 'Synthetic chemistry analyzer',
  equipment_model: 'SYNTHETIC MODEL',
  adapter_key: 'hl7_v2',
  protocol_code: 'hl7_v2',
  mapping_profile: {
    analyte_codes: { 'SYNTHETIC-GLU': 'glucose' },
    unit_codes: { 'SYNTHETIC-GLU': { 'SYNTHETIC-MMOL': 'mmol_l' } },
    flag_codes: {},
  },
  simulator_validation_status: 'PASS' as const,
  physical_validation_status: 'NOT_RUN' as const,
};

function renderPanel() {
  return render(
    <ThemeProvider>
      <LabClinicalConfigurationPanel onClose={vi.fn()} />
    </ThemeProvider>,
  );
}

describe('LabClinicalConfigurationPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.user = null;
    mocks.api.get.mockImplementation((path: string) => Promise.resolve({
      data: path === '/clinic/lab-clinical-configurations' ? [] : [],
    }));
    mocks.api.post.mockResolvedValue({ data: pendingVersion });
    mocks.api.put.mockResolvedValue({ data: pendingVersion });
  });

  it('shows approval only to the configured primary or substitute Lab physician', async () => {
    mocks.user = { id: 8, role: 'Lab', is_active: true };
    mocks.api.get.mockImplementation((path: string) => Promise.resolve({
      data: path === '/clinic/lab-clinical-configurations' ? [pendingVersion] : [],
    }));

    renderPanel();

    expect(await screen.findByText('labClinicalConfig.version')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'labClinicalConfig.approve' }));
    await waitFor(() => {
      expect(mocks.api.post).toHaveBeenCalledWith(
        '/clinic/lab-clinical-configurations/21/approve',
      );
    });
  });

  it('does not expose draft editing or approval actions to an unassigned user', async () => {
    mocks.user = { id: 42, role: 'Lab', is_active: true };
    mocks.api.get.mockImplementation((path: string) => Promise.resolve({
      data: path === '/clinic/lab-clinical-configurations' ? [pendingVersion] : [],
    }));

    renderPanel();

    await screen.findByText('labClinicalConfig.version');
    expect(screen.queryByRole('button', { name: 'labClinicalConfig.approve' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'labClinicalConfig.newDraft' })).toBeNull();
  });

  it('lets the assigned Lab physician approve an analyzer mapping version', async () => {
    mocks.user = { id: 8, role: 'Lab', is_active: true };
    mocks.api.get.mockImplementation((path: string) => Promise.resolve({
      data: path === '/clinic/lab-clinical-configurations'
        ? [pendingVersion]
        : [pendingAnalyzerMapping],
    }));

    renderPanel();

    expect(await screen.findByText('labClinicalConfig.analyzerProfile')).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC-GLU/)).toBeInTheDocument();
    expect(screen.getByText('labClinicalConfig.physicalStatus')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {
      name: 'labClinicalConfig.approveAnalyzerMapping',
    }));
    await waitFor(() => {
      expect(mocks.api.post).toHaveBeenCalledWith(
        '/clinic/lab-equipment-integration-versions/51/clinical-approval',
      );
    });
  });

  it('lets Admin save a new draft without seeding any clinic clinical values', async () => {
    mocks.user = { id: 2, role: 'Admin', is_active: true };
    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'labClinicalConfig.newDraft' }));
    fireEvent.change(screen.getByLabelText('labClinicalConfig.primary'), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText('labClinicalConfig.substitute'), { target: { value: '8' } });
    fireEvent.click(screen.getByRole('button', { name: 'labClinicalConfig.saveDraft' }));

    await waitFor(() => {
      expect(mocks.api.post).toHaveBeenCalledWith(
        '/clinic/lab-clinical-configurations',
        expect.objectContaining({
          primary_lab_physician_user_id: 7,
          substitute_lab_physician_user_id: 8,
          configuration_snapshot: expect.objectContaining({
            reference_intervals: [],
            critical_values: [],
            qc_rules: [],
          }),
        }),
      );
    });
  });
});
