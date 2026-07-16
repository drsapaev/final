/**
 * StepProgressIndicator — extracted from AppointmentWizardV2.jsx (PR-45 / High-15).
 *
 * Visual progress bar showing the current step in the wizard.
 * Previously inline in AppointmentWizardV2.jsx (lines 2897-2921).
 *
 * UX Audit R-2.3: добавлены подписи шагов (Пациент / Услуги) +
 * статусы (active/completed/pending) + CSS-классы вместо inline-стилей.
 * Раньше: только 4-пиксельные полоски без текста — Nielsen #1 (visibility).
 */
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

const STEP_LABELS = {
  ru: ['Пациент', 'Услуги'],
  uz: ['Bemor', 'Xizmatlar'],
  en: ['Patient', 'Services'],
};

const StepProgressIndicator = ({ currentStep, totalSteps, language = 'ru' }) => {
  const { t } = useTranslation();
  const labels = (STEP_LABELS[language] || STEP_LABELS.ru).slice(0, totalSteps);
  return (
    <ol className="wizard-progress" aria-label="Шаги мастера записи">
      {labels.map((label, i) => {
        const step = i + 1;
        const state = currentStep > step ? 'completed' : currentStep === step ? 'active' : 'pending';
        return (
          <li key={step} className={`wizard-progress__item wizard-progress__item--${state}`}>
            <span className="wizard-progress__dot" aria-hidden="true">{step}</span>
            <span className="wizard-progress__label">{label}</span>
          </li>
        );
      })}
    </ol>
  );
};

StepProgressIndicator.propTypes = {
  currentStep: PropTypes.number.isRequired,
  totalSteps: PropTypes.number.isRequired,
  language: PropTypes.oneOf(['ru', 'uz', 'en']),
};

export default StepProgressIndicator;
