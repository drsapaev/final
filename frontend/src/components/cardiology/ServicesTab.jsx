/**
 * ServicesTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "Услуги" (services) tab content — a read-only catalog of
 * cardiology services via DoctorServiceSelector.
 *
 * All state stays in the parent. This is a presentational wrapper.
 */

import DoctorServiceSelector from '../doctor/DoctorServiceSelector';

export function ServicesTab() {
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
