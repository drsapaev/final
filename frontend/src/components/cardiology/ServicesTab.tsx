import React from 'react';

/**
 * ServicesTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "Услуги" (services) tab content — a read-only catalog of
 * cardiology services via DoctorServiceSelector.
 *
 * CARDSVC-FE-002 (audit 3886): the tab is explicitly read-only — no
 * selection owner and no price editing — so the selector must render a
 * non-interactive catalog instead of pseudo-selectable cards.
 *
 * All state stays in the parent. This is a presentational wrapper.
 */

import DoctorServiceSelector from '../doctor/DoctorServiceSelector';
import { useTranslation } from '../../i18n/useTranslation';

export function ServicesTab(): React.JSX.Element | null {
  const { t } = useTranslation();
  return (
    <div className="cardio-w-full-visible">
      <DoctorServiceSelector
        specialty="cardiology"
        selectedServices={[]}
        canEditPrices={false}
        readOnly
      />
    </div>
  );
}

export default ServicesTab;
