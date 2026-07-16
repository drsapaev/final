// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * ServicesTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "Услуги" (services) tab content — a read-only catalog of
 * cardiology services via DoctorServiceSelector.
 *
 * All state stays in the parent. This is a presentational wrapper.
 */

import DoctorServiceSelector from '../doctor/DoctorServiceSelector';
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
