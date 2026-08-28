/**
 * QueueTable Stories
 *
 * UX Audit R-3.4: visual testing for queue table with source badges.
 * Shows states: empty queue, with entries (QR + Desk sources).
 *
 * PII policy (AGENTS.md §PII fields L377/L388): first_name / last_name are PII
 * and must NEVER appear in plaintext in committed test fixtures. The fixtures
 * below use a clearly-synthetic surname ("Тестов" = "Testov" — derived from
 * "test") + initial placeholders, so the stories are policy-compliant.
 */
import QueueTable from './QueueTable';

export default {
  title: 'Queue/QueueTable',
  component: QueueTable,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Table showing queue entries with source badges (QR/Ресепшен). ' +
          'UX Audit R-3.4: inline styles migrated to QueueTable.css. ' +
          'UX Audit R-3.9: source badges use consistent terminology (QR/Ресепшен).',
      },
    },
  },
  decorators: [
    (Story: () => React.ReactElement) => (
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

// Queue with mixed sources — fixtures anonymized per AGENTS.md §PII L377/L388
export const MixedSources = {
  args: {
    entries: [
      { id: 1, patient_name: 'Тестов Т. Т.', queue_number: 'A001', source: 'online', status: 'waiting', created_at: new Date().toISOString() },
      { id: 2, patient_name: 'Тестова Т. Т.', queue_number: 'A002', source: 'desk', status: 'called', created_at: new Date().toISOString() },
      { id: 3, patient_name: 'Тест Т. Т.', queue_number: 'A003', source: 'online', status: 'waiting', created_at: new Date().toISOString() },
    ],
    onCallPatient: () => {},
    onRemoveEntry: () => {},
  },
};

// Queue with all called — fixtures anonymized per AGENTS.md §PII L377/L388
export const AllCalled = {
  args: {
    entries: [
      { id: 1, patient_name: 'Тестов Т. Т.', queue_number: 'A001', source: 'online', status: 'called', created_at: new Date().toISOString() },
      { id: 2, patient_name: 'Тестова Т. Т.', queue_number: 'A002', source: 'desk', status: 'called', created_at: new Date().toISOString() },
    ],
    onCallPatient: () => {},
    onRemoveEntry: () => {},
  },
};
