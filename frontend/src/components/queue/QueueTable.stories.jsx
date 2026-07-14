/**
 * QueueTable Stories
 *
 * UX Audit R-3.4: visual testing for queue table with source badges.
 * Shows states: empty queue, with entries (QR + Desk sources).
 */
import QueueTable from './QueueTable';

export default {
  title: 'Queue/QueueTable',
  component: QueueTable,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Table showing queue entries with source badges (QR/Desk). ' +
          'UX Audit R-3.4: inline styles migrated to RefundRequestsTable.css pattern. ' +
          'UX Audit R-3.9: source badges use consistent terminology (QR/Ресепшен).',
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

// Empty queue
export const EmptyQueue = {
  args: {
    entries: [],
    onCallPatient: () => {},
    onRemoveEntry: () => {},
  },
};

// Queue with mixed sources
export const MixedSources = {
  args: {
    entries: [
      { id: 1, patient_name: 'Иванов Иван', queue_number: 'A001', source: 'online', status: 'waiting', created_at: new Date().toISOString() },
      { id: 2, patient_name: 'Петров Петр', queue_number: 'A002', source: 'desk', status: 'called', created_at: new Date().toISOString() },
      { id: 3, patient_name: 'Сидорова Анна', queue_number: 'A003', source: 'online', status: 'waiting', created_at: new Date().toISOString() },
    ],
    onCallPatient: () => {},
    onRemoveEntry: () => {},
  },
};

// Queue with all called
export const AllCalled = {
  args: {
    entries: [
      { id: 1, patient_name: 'Иванов Иван', queue_number: 'A001', source: 'online', status: 'called', created_at: new Date().toISOString() },
      { id: 2, patient_name: 'Петров Петр', queue_number: 'A002', source: 'desk', status: 'called', created_at: new Date().toISOString() },
    ],
    onCallPatient: () => {},
    onRemoveEntry: () => {},
  },
};
