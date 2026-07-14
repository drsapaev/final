/**
 * CancelDialog Stories
 *
 * UX Audit R-2.1: visual testing for cancel payment dialog
 * with required reason (min 10 chars) and payment context.
 */
import CancelDialog from './CancelDialog';

export default {
  title: 'Dialogs/CancelDialog',
  component: CancelDialog,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Dialog for cancelling a payment. ' +
          'Requires reason (min 10 chars). Shows payment context (ID, patient, amount). ' +
          'UX Audit R-2.1: error prevention on destructive financial action.',
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
};

export const EmptyReason = {
  args: {
    open: true,
    paymentContext: {
      id: 3001,
      patient: 'Иванов Иван Иванович',
      amount: 150000,
    },
    cancelReason: '',
    onClose: () => {},
    onCancel: () => {},
  },
};

export const ShortReason = {
  args: {
    open: true,
    paymentContext: {
      id: 3001,
      patient: 'Иванов Иван Иванович',
      amount: 150000,
    },
    cancelReason: 'коротко',
    onClose: () => {},
    onCancel: () => {},
  },
};

export const ValidReason = {
  args: {
    open: true,
    paymentContext: {
      id: 3001,
      patient: 'Иванов Иван Иванович',
      amount: 150000,
    },
    cancelReason: 'Пациент отказался от услуги по личным причинам',
    onClose: () => {},
    onCancel: () => {},
  },
};
