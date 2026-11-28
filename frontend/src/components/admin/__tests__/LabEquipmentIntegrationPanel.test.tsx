import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { api } from '../../../api/client';
import { ThemeProvider } from '@/contexts/ThemeContext';
import LabEquipmentIntegrationPanel from '../LabEquipmentIntegrationPanel';

vi.mock('../../../api/client', () => {
  const client = {
    get: vi.fn(),
    post: vi.fn(),
  };
  return { api: client, default: client };
});

const draftProfile = {
  id: 17,
  equipment_id: 31,
  device_role: 'label_printer' as const,
  versions: [
    {
      id: 42,
      version_no: 1,
      status: 'DRAFT' as const,
      adapter_key: 'manual',
      protocol_code: 'manual',
      transport_code: 'file_drop',
      mapping_profile: {},
      transport_settings: {},
      device_settings: {
        label_width_mm: 100,
        label_height_mm: 40,
        barcode_symbology: 'Code128',
      },
      simulator_validation_status: 'PASS' as const,
      simulator_evidence_ref: 'synthetic-test://sha256/fixture',
      physical_validation_status: 'NOT_RUN' as const,
      physical_evidence_ref: null,
    },
  ],
};

describe('LabEquipmentIntegrationPanel', () => {
  it('keeps synthetic and physical validation separate before activation', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: draftProfile } as never);

    render(
      <ThemeProvider>
        <LabEquipmentIntegrationPanel
          equipmentId={31}
          equipmentName="Synthetic label device"
          t={(key) => key.replace('admin2.', '')}
          onClose={vi.fn()}
        />
      </ThemeProvider>,
    );

    expect(await screen.findByText('lab_int_synthetic_only')).toBeTruthy();
    expect(screen.getByLabelText('lab_int_synthetic_message')).toHaveAttribute(
      'placeholder',
      'lab_int_probe_label_printer_placeholder',
    );
    expect(screen.getByText(/lab_int_physical_status: lab_int_not_run/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /lab_int_activate/ })).toBeDisabled();
  });

  it('saves the selected label default in the version settings', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { ...draftProfile, versions: [] },
    } as never);
    vi.mocked(api.post).mockResolvedValue({ data: {} } as never);

    render(
      <ThemeProvider>
        <LabEquipmentIntegrationPanel
          equipmentId={31}
          equipmentName="Synthetic label device"
          t={(key) => key.replace('admin2.', '')}
          onClose={vi.fn()}
        />
      </ThemeProvider>,
    );

    const makeDefault = await screen.findByRole('checkbox', {
      name: 'lab_int_default_label_profile',
    });
    fireEvent.click(makeDefault);
    const deviceSettings = JSON.parse(
      (screen.getByLabelText('lab_int_device_settings') as HTMLTextAreaElement).value,
    ) as Record<string, unknown>;
    expect(deviceSettings.default_for_lab_labels).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /lab_int_create_version/ }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/clinic/lab-equipment-integrations/17/versions',
        expect.objectContaining({
          device_settings: expect.objectContaining({
            label_width_mm: 100,
            default_for_lab_labels: true,
          }),
        }),
      );
    });
  });
});
