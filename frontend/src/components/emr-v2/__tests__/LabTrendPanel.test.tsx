import '@testing-library/jest-dom';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { WorkspaceLabValue } from '@/api/emrWorkspace';
import i18n from '@/i18n';
import { LabTrendPanel } from '../workspace/LabTrendPanel';

function measurement(id: number, value: string, key = 'serum-k-v1', unit = 'mmol/L', fieldKey = 'potassium'): WorkspaceLabValue {
  return {
    instance_id: id,
    name: 'Potassium',
    value,
    unit,
    finalized_at: null,
    abnormal: false,
    comparison: { key, template_name: 'Chemistry', template_version: 1, field_key: fieldKey, value },
  };
}

beforeEach(async () => {
  await i18n.changeLanguage('en');
});

describe('LabTrendPanel', () => {
  it('requires matching comparison keys across two dated visits', () => {
    render(<LabTrendPanel visits={[
      { id: 10, date: '2026-01-10', values: [measurement(101, '3.20'), measurement(102, '4.20')] },
      { id: 20, date: '2026-01-20', values: [measurement(201, '3.50', 'serum-k-v2')] },
      { id: 30, date: '2026-01-30', values: [measurement(301, '20', 'serum-k-custom-unit', 'mg/L')] },
      { id: 31, date: '2026-01-31', values: [{ ...measurement(311, '3.70'), comparison: null }] },
      { id: 40, date: null, values: [measurement(401, '3.80')] },
    ]} onOpenReport={vi.fn()} />);

    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('No comparable results across dated visits');
  });

  it('omits the trend section and status when there are no laboratory results', () => {
    render(<LabTrendPanel visits={[{ id: 10, date: '2026-01-10', values: [] }]} onOpenReport={vi.fn()} />);

    expect(screen.queryByRole('region', { name: 'Laboratory trends' })).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('distinguishes otherwise identical series labels using their source field keys', () => {
    render(<LabTrendPanel visits={[
      { id: 10, date: '2026-01-10', values: [
        measurement(101, '3.20', 'serum-k-v1', 'mmol/L', 'potassium_primary'),
        measurement(102, '3.50', 'duplicate-k-v1', 'mmol/L', 'potassium_secondary'),
      ] },
      { id: 20, date: '2026-01-20', values: [
        measurement(201, '3.40', 'serum-k-v1', 'mmol/L', 'potassium_primary'),
        measurement(202, '3.70', 'duplicate-k-v1', 'mmol/L', 'potassium_secondary'),
      ] },
    ]} onOpenReport={vi.fn()} />);

    expect(screen.getByRole('option', { name: /potassium_primary$/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /potassium_secondary$/ })).toBeInTheDocument();
  });

  it('opens the exact source before showing comparable values in date order', () => {
    const openReport = vi.fn();
    render(<LabTrendPanel visits={[
      { id: 20, date: '2026-01-20', values: [measurement(201, '0.00')] },
      { id: 10, date: '2026-01-10', values: [measurement(101, '3.20')] },
    ]} onOpenReport={openReport} />);
    expect(screen.getByRole('option', { name: 'Potassium (mmol/L) · Chemistry · Version 1' })).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox', { name: 'Measurement to compare' }), {
      target: { value: 'serum-k-v1' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Report #201' }));

    expect(openReport).toHaveBeenCalledWith(201);
    expect(screen.queryByText('0.00 mmol/L')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', { name: /specimen types and testing methods are comparable/ }));

    const [earlier, later] = screen.getAllByRole('listitem');
    expect(within(earlier).getByText('2026-01-10')).toBeInTheDocument();
    expect(within(earlier).getByText('3.20 mmol/L')).toBeInTheDocument();
    expect(within(later).getByText('2026-01-20')).toBeInTheDocument();
    expect(within(later).getByText('0.00 mmol/L')).toBeInTheDocument();
  });

  it('requires fresh confirmation when the selected series receives a corrected report', () => {
    const first = { id: 10, date: '2026-01-10', values: [measurement(101, '3.20')] };
    const openReport = vi.fn();
    const { rerender } = render(<LabTrendPanel visits={[
      first, { id: 20, date: '2026-01-20', values: [measurement(201, '3.40')] },
    ]} onOpenReport={openReport} />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'serum-k-v1' } });
    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByText('3.40 mmol/L')).toBeInTheDocument();

    rerender(<LabTrendPanel visits={[
      first, { id: 20, date: '2026-01-20', values: [measurement(202, '3.55')] },
    ]} onOpenReport={openReport} />);

    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.queryByText('3.55 mmol/L')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Report #202' })).toBeInTheDocument();
  });
});
