/**
 * ServicesTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "Услуги" (services) tab content — a read-only catalog of
 * cardiology services via DoctorServiceSelector.
 *
 * All state stays in the parent. This is a presentational wrapper.
 */

import PropTypes from 'prop-types';
import DoctorServiceSelector from '../doctor/DoctorServiceSelector';

/**
 * @param {Object} props
 * @param {Function} props.getSpacing - Theme spacing getter (unused but
 *   kept for API consistency with other tab components)
 */
export function ServicesTab({ getSpacing: _getSpacing }) {
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

ServicesTab.propTypes = {
  getSpacing: PropTypes.func,
};

export default ServicesTab;
