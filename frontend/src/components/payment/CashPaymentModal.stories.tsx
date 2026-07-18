// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * CashPaymentModal Stories
 *
 * UX Audit R-1.2: visual testing for cash payment modal with quick denominations.
 * Shows states: default (cash method), with change due, insufficient funds.
 */
import CashPaymentModal from './CashPaymentModal';
import i18n from '../../i18n';

// i18n: stories use the i18n singleton directly (no hook available at module-level).
// Storybook args are resolved at module-load time using the current language.
const t = (key, params) => i18n.t(key, params);

export default {
  title: 'Payment/CashPaymentModal',
  component: CashPaymentModal,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: t('payment.pay_story_docs_description', {
          noChangeBtn: t('payment.pay_story_no_change_btn'),
        }),
      },
    },
  },
  decorators: [
    (Story) => (
      <div style={{ padding: '20px', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
  argTypes: {
    appointment: {
      control: 'object',
      description: 'Appointment data',
    },
  },
};

// Default cash payment
export const DefaultCash = {
  args: {
    appointment: {
      id: 1001,
      patient_name: t('payment.pay_story_patient_1'),
      patient_id: 101,
      department: t('payment.pay_story_department_1'),
      appointment_date: '2026-07-14',
      appointment_time: '10:00',
      total_amount: 150000,
      remaining_amount: 150000,
      payment_amount: 150000,
    },
    onProcessPayment: () => alert('Payment processed'),
    onClose: () => alert('Modal closed'),
  },
};

// Large amount
export const LargeAmount = {
  args: {
    appointment: {
      id: 1002,
      patient_name: t('payment.pay_story_patient_2'),
      patient_id: 102,
      department: t('payment.pay_story_department_2'),
      appointment_date: '2026-07-14',
      appointment_time: '11:30',
      total_amount: 850000,
      remaining_amount: 850000,
      payment_amount: 850000,
    },
    onProcessPayment: () => {},
    onClose: () => {},
  },
};
