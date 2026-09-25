import { useMemo } from 'react';
import { screen, waitFor } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../test/renderWithProviders';
import { DERMATOLOGY_PANEL_TABS, getDermatologyTabAliases } from '../../pages/dermatologyTabAliases';
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

function DermatologyPanelStateProbe() {
  const location = useLocation();
  const tabAliases = useMemo(
    () => getDermatologyTabAliases(location.search),
    [location.search]
  );
  const { activeTab } = useDoctorPanelState({
    defaultTab: 'queue',
    visitDeepLinkTab: 'visit',
    patientDeepLinkTab: 'patients',
    validTabs: [...DERMATOLOGY_PANEL_TABS],
    tabAliases,
  });

  return <output data-testid="dermatology-panel-state">{`${activeTab}|${location.search}`}</output>;
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

describe('useDoctorPanelState dermatologist legacy tabs', () => {
  it.each([
    [
      '/doctor/dermatology?tab=history&patientId=41',
      'patients',
      '?tab=patients&patientId=41',
    ],
    [
      '/doctor/dermatology?tab=appointments&patientId=41',
      'queue',
      '?tab=queue&patientId=41',
    ],
    [
      '/doctor/dermatology?tab=appointments&patientId=41&visitId=72',
      'visit',
      '?tab=visit&patientId=41&visitId=72',
    ],
    [
      '/doctor/dermatology?tab=photos&patientId=41&visit_id=72',
      'visit',
      '?tab=visit&patientId=41&visit_id=72',
    ],
    ['/doctor/dermatology?tab=ai', 'visit', '?tab=visit'],
    ['/doctor/dermatology?tab=skin', 'visit', '?tab=visit'],
    ['/doctor/dermatology?tab=cosmetic', 'visit', '?tab=visit'],
    ['/doctor/dermatology?tab=services', 'visit', '?tab=visit'],
  ])('replaces %s with the visible tab and preserves the deep-link ids', async (entry, expectedTab, expectedSearch) => {
    renderWithProviders(<DermatologyPanelStateProbe />, {
      routerProps: { initialEntries: [entry] },
    });

    await waitFor(() => {
      expect(screen.getByTestId('dermatology-panel-state')).toHaveTextContent(
        `${expectedTab}|${expectedSearch}`
      );
    });
  });
});
