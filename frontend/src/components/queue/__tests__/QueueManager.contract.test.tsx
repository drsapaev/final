import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { normalizeSource } from '../../../test/contracts/source-contract-helper';

const ROOT = path.resolve(process.cwd(), 'src');
const read = (filePath: string) => normalizeSource(fs.readFileSync(path.join(ROOT, filePath), 'utf8'));

describe('Queue manager command contract', () => {
  it('keeps registrar queue call-next as a backend-owned command, not a row command', () => {
    const tableSource = read('components/queue/QueueTable.tsx');
    const managerSource = read('components/queue/ModernQueueManager.tsx');

    expect(managerSource).toContain('callNextPatientInQueue');
    expect(managerSource).toContain('onClick={callPatient}');
    expect(managerSource).toContain('title="Backend call-next command"');
    expect(managerSource).not.toContain('onCallPatient={callPatient}');

    expect(tableSource).not.toContain('Button');
    expect(tableSource).not.toContain('{false && (');
    expect(tableSource).not.toContain('onCallPatient(entry)');
    expect(tableSource).not.toContain('entry.status === \'waiting\' && (');
  });

  it('uses backend-provided available specialists for queue doctor options', () => {
    const managerSource = read('components/queue/ModernQueueManager.tsx');

    expect(managerSource).toContain('specialists,');
    expect(managerSource).toContain('if (!Array.isArray(specialists) || specialists.length === 0) return []');
    expect(managerSource).toContain('d.specialty_display || d.specialty');
    expect(managerSource).not.toContain('fetch(\'/api/v1/queues/profiles/public\')');
    expect(managerSource).not.toContain('allowedSpecialties');
    expect(managerSource).not.toContain('normalizeSpecialty');
  });

  it('keeps registrar online queue doctor selection explicit before doctor-specific commands load', () => {
    const registrarSource = read('pages/RegistrarPanel.tsx');
    // PR-UI-13-5: the calendar slice (with the explicit doctor-selection note)
    // moved to pages/registrar/useRegistrarCalendar.ts.
    const calendarSource = read('pages/registrar/useRegistrarCalendar.ts');
    const queueViewSource = read('pages/registrar/views/QueueView.tsx');
    const managerSource = read('components/queue/ModernQueueManager.tsx');
    const tableSource = read('components/queue/QueueTable.tsx');

    expect(calendarSource).toContain('Выбор врача остаётся явным: URL-параметр или ручной выбор в очереди');
    // Decomp 6a: selectedDoctor prop moved to QueueView.jsx
    expect(queueViewSource).toContain('selectedDoctor={searchParams.get(\'doctor\') || \'\'}');

    expect(managerSource).toContain('const [internalDoctor, setInternalDoctor] = useState(\'\')');
    expect(managerSource).toContain('const effectiveDoctor = selectedDoctor !== undefined && selectedDoctor !== \'\' ? selectedDoctor : internalDoctor');
    expect(managerSource).toContain('if (!effectiveDoctor) {');
    expect(managerSource).not.toContain('setInternalDoctor(doctorOptions[0]');
    expect(managerSource).not.toContain('setInternalDoctor(specialists[0]');

    expect(tableSource).toContain('if (!effectiveDoctor) {');
    expect(tableSource).toContain('t?.selectDoctor || \'Выберите специалиста\'');
  });

  // RQ-11 (F-10): скачанный QR воспринимался как плакат, но токен имеет
  // ограниченный срок. Диалог обязан различать valid/expired/unspecified,
  // а скачиваемый PNG — нести подпись срока и пометку временного кода.
  it('keeps QR expiry honest in the dialog and on the downloaded PNG', () => {
    const managerSource = read('components/queue/ModernQueueManager.tsx');
    const helperSource = read('components/queue/qrExpiry.ts');

    // Диалог: срок классифицируется по серверному expires_at через pure-хелпер.
    expect(managerSource).toContain('resolveQrExpiryView');
    expect(managerSource).toContain('mqm_qr_expired');
    expect(managerSource).toContain('mqm_qr_limited');
    expect(managerSource).toContain('mqm-qr-expiry-expired');

    // Скачивание: PNG получает подписи срока/истечения и пометку временного кода.
    expect(managerSource).toContain('buildQrDownloadCaptions');
    expect(managerSource).toContain('mqm_qr_download_note');
    expect(managerSource).toContain('mqm_qr_download_expired');

    // Жесткая ru-RU локаль в expiry-строке заменена каноническими
    // dateUtils-форматтерами (клиник-таймзона Asia/Tashkent).
    expect(managerSource).not.toContain('toLocaleString(\'ru-RU\'');

    // Хелпер — presentation-only: не меняет TTL/защиты/контракт сервера.
    expect(helperSource).toContain('\'valid\' | \'expired\' | \'unspecified\'');
    expect(helperSource).not.toContain('expires_hours');
    expect(helperSource).not.toContain('single_use');
  });
});
