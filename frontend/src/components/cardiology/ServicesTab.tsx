import React from 'react';

/**
 * ServicesTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "Услуги" (services) tab content — a read-only catalog of
 * cardiology services via DoctorServiceSelector.
 *
 * All state stays in the parent. This is a presentational wrapper.
 */

import DoctorServiceSelectorRaw from '../doctor/DoctorServiceSelector';
const DoctorServiceSelector = DoctorServiceSelectorRaw as unknown as React.ComponentType<Record<string, unknown>>;
import { useTranslation } from '../../i18n/useTranslation';

export function ServicesTab() {
  const { t } = useTranslation();
  return (
    <div className="cardio-w-full-visible">
      <DoctorServiceSelector
        specialty="cardiology"
        selectedServices={[]}
        canEditPrices={false}
      />
    </div>
  );
}

export default ServicesTab;
