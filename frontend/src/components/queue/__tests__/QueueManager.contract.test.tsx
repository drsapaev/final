import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');
const read = (filePath) => fs.readFileSync(path.join(ROOT, filePath), 'utf8');

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
    const queueViewSource = read('pages/registrar/views/QueueView.tsx');
    const managerSource = read('components/queue/ModernQueueManager.tsx');
    const tableSource = read('components/queue/QueueTable.tsx');

    expect(registrarSource).toContain('Выбор врача остаётся явным: URL-параметр или ручной выбор в очереди');
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
});
