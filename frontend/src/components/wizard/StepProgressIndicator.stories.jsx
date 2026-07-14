/**
 * StepProgressIndicator Stories
 *
 * UX Audit R-2.3: visual testing for wizard step progress indicator.
 * Shows 3 states: step 1 active, step 2 active, both completed.
 */
import StepProgressIndicator from './StepProgressIndicator';

export default {
  title: 'Wizard/StepProgressIndicator',
  component: StepProgressIndicator,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Visual progress bar showing the current step in the wizard. ' +
          'Features: step labels (Пациент/Услуги), 3 states (pending/active/completed), ' +
          'ARIA radiogroup pattern, responsive (labels hidden on <480px).',
      },
    },
  },
  argTypes: {
    currentStep: {
      control: { type: 'number', min: 1, max: 2, step: 1 },
      description: 'Current active step (1-based)',
    },
    totalSteps: {
      control: { type: 'number', min: 1, max: 5, step: 1 },
      description: 'Total number of steps',
    },
    language: {
      control: { type: 'select' },
      options: ['ru', 'uz', 'en'],
      description: 'UI language for step labels',
    },
  },
};

// Step 1 active — patient data entry
export const Step1Active = {
  args: {
    currentStep: 1,
    totalSteps: 2,
    language: 'ru',
  },
};

// Step 2 active — services selection
export const Step2Active = {
  args: {
    currentStep: 2,
    totalSteps: 2,
    language: 'ru',
  },
};

// Uzbek localization
export const UzbekLanguage = {
  args: {
    currentStep: 1,
    totalSteps: 2,
    language: 'uz',
  },
};

// English localization
export const EnglishLanguage = {
  args: {
    currentStep: 1,
    totalSteps: 2,
    language: 'en',
  },
};
