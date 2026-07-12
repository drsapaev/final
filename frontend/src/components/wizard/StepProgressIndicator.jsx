/**
 * StepProgressIndicator — extracted from AppointmentWizardV2.jsx (PR-45 / High-15).
 *
 * Visual progress bar showing the current step in the wizard.
 * Previously inline in AppointmentWizardV2.jsx (lines 2897-2921).
 */
import PropTypes from 'prop-types';

const StepProgressIndicator = ({ currentStep, totalSteps }) => {
  return (
    <div style={{
      display: 'flex',
      gap: 'var(--mac-spacing-2)',
      marginBottom: 'var(--mac-spacing-3)',
      padding: '0 4px',
    }}>
      {Array.from({ length: totalSteps }, (_, i) => i + 1).map((step) => (
        <div
          key={step}
          style={{
            flex: 1,
            height: '4px',
            borderRadius: 'var(--mac-radius-sm)',
            backgroundColor: currentStep >= step
              ? 'var(--mac-accent-blue, #007aff)'
              : 'color-mix(in srgb, var(--mac-text-secondary, #8e8e93), transparent 70%)',
            transition: 'background-color 200ms ease',
          }}
        />
      ))}
    </div>
  );
};

StepProgressIndicator.propTypes = {
  currentStep: PropTypes.number.isRequired,
  totalSteps: PropTypes.number.isRequired,
};

export default StepProgressIndicator;
