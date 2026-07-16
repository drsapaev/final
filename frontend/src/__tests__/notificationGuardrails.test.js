import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');

const NOTIFICATION_FILES = [
  'contexts/NotificationCenterContext.tsx',
  'contexts/NotificationWebSocketContext.tsx',
  'components/notifications/NotificationInbox.jsx',
  'components/notifications/RoleNotificationCenter.jsx',
  'components/chat/NotificationPrompt.jsx'
];

const PANEL_FILES = [
  'pages/RegistrarPanel.jsx',
  'pages/CardiologistPanelUnified.jsx',
  'pages/DentistPanelUnified.jsx',
  'pages/DermatologistPanelUnified.jsx',
  'pages/LabPanel.jsx'
];

function read(filePath) {
  return fs.readFileSync(path.join(ROOT, filePath), 'utf8');
}

describe('notification guardrails', () => {
  it('keeps notification surfaces on the shared adapter path', () => {
    for (const filePath of NOTIFICATION_FILES) {
      const content = read(filePath);
      expect(content).not.toMatch(/from ['"]react-toastify['"]/);
      expect(content).not.toContain('alert(');
    }

    const prompt = read('components/chat/NotificationPrompt.jsx');
    expect(prompt).toContain('notify.warning(');
    expect(prompt).toContain('notify.error(');

    for (const filePath of PANEL_FILES) {
      const content = read(filePath);
      expect(content).toContain('RoleNotificationCenter');
      expect(content).not.toMatch(/react-toastify/);
    }

    const registrar = read('pages/RegistrarPanel.jsx');
    expect(registrar).toContain('loadAppointmentsInFlightRef');
    expect(registrar).toContain('autoRefreshCooldownUntilRef');
  });

  it('keeps notification center loaders stable to avoid fetch loops', () => {
    const context = read('contexts/NotificationCenterContext.tsx');
    const roleCenter = read('components/notifications/RoleNotificationCenter.jsx');

    expect(context).toContain('const inboxRef = useRef(inbox);');
    expect(context).toContain('const unreadSnapshotRef = useRef(unreadSnapshot);');
    expect(context).toContain('return unreadSnapshotRef.current;');
    expect(context).toContain('return inboxRef.current;');
    expect(context).toContain('[refreshUnreadCounts]');
    expect(context).not.toContain('[inbox, refreshUnreadCounts]');
    expect(context).not.toContain('[unreadSnapshot]');

    expect(roleCenter).toContain('useEffect(() => {');
    expect(roleCenter).toContain('[runLoadNotifications, userRole]');
  });

  it('keeps registrar table action visibility on backend-provided actions', () => {
    const table = read('components/tables/EnhancedAppointmentsTable.jsx');

    expect(table).toContain('getBackendActionAvailability');
    expect(table).toContain('can_mark_paid');
    expect(table).toContain('can_start_visit');
    expect(table).toContain('can_print_ticket');
    expect(table).toContain('can_complete');
    expect(table).toContain('available_actions');
    expect(table).toContain('{canPay &&');
    expect(table).not.toContain('{!isDoctorView && (() => {');
    const quote = String.fromCharCode(39);
    expect(table).not.toContain(
      'status === ' + quote + 'queued' + quote + ' && paymentStatus !== ' + quote + 'paid' + quote
    );
  });
});
