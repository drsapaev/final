import { screen, waitFor } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../test/renderWithProviders';
import { useDoctorPanelState } from '../useDoctorPanelState';

const validTabs = ['queue', 'visit', 'patients', 'ai-assistant'];
const tabAliases = { photos: 'patients', visits: 'visit', appointments: 'patients' };

function PanelStateProbe() {
  const { activeTab, handleTabChange } = useDoctorPanelState({
    defaultTab: 'queue',
    visitDeepLinkTab: 'visit',
    patientDeepLinkTab: 'patients',
    validTabs,
    tabAliases,
  });
  const location = useLocation();

  return (
    <>
      <output data-testid="panel-state">{`${activeTab}|${location.search}`}</output>
      <button type="button" onClick={() => handleTabChange('photos')}>legacy photo action</button>
    </>
  );
}

describe('useDoctorPanelState dentist legacy tabs', () => {
  it.each([
    ['/doctor/dentistry?tab=photos', 'patients'],
    ['/doctor/dentistry?tab=appointments', 'patients'],
    ['/doctor/dentistry?tab=visits', 'visit'],
    ['/doctor/dentistry?tab=unknown', 'queue'],
  ])('normalizes %s to %s and replaces the URL', async (entry, expectedTab) => {
    renderWithProviders(<PanelStateProbe />, {
      routerProps: { initialEntries: [entry] },
    });

    await waitFor(() => {
      expect(screen.getByTestId('panel-state')).toHaveTextContent(`${expectedTab}|?tab=${expectedTab}`);
    });
  });

  it('normalizes unsupported programmatic tab changes too', async () => {
    renderWithProviders(<PanelStateProbe />, {
      routerProps: { initialEntries: ['/doctor/dentistry?tab=queue'] },
    });

    screen.getByRole('button', { name: 'legacy photo action' }).click();

    await waitFor(() => {
      expect(screen.getByTestId('panel-state')).toHaveTextContent('patients|?tab=patients');
    });
  });
});
