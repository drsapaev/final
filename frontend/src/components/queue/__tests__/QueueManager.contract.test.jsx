import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');
const read = (filePath) => fs.readFileSync(path.join(ROOT, filePath), 'utf8');

describe('Queue manager command contract', () => {
  it('keeps registrar queue call-next as a backend-owned command, not a row command', () => {
    const tableSource = read('components/queue/QueueTable.jsx');
    const managerSource = read('components/queue/ModernQueueManager.jsx');

    expect(managerSource).toContain('callNextPatientInQueue');
    expect(managerSource).toContain('onClick={callPatient}');
    expect(managerSource).toContain('title="Backend call-next command"');
    expect(managerSource).not.toContain('onCallPatient={callPatient}');

    expect(tableSource).not.toContain('Button');
    expect(tableSource).not.toContain('{false && (');
    expect(tableSource).not.toContain('onCallPatient(entry)');
    expect(tableSource).not.toContain("entry.status === 'waiting' && (");
  });
});
