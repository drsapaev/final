import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { normalizeSource } from '../../../test/contracts/source-contract-helper';

const sourcePath = path.resolve(
  process.cwd(),
  'src/components/admin/AllFreeApproval.tsx'
);

const readSource = () => normalizeSource(fs.readFileSync(sourcePath, 'utf8'));

const sourceSlice = (source: string, startMarker: string, endMarker: string) => {
  const start = source.indexOf(normalizeSource(startMarker));
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(normalizeSource(endMarker), start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('AllFreeApproval action contract', () => {
  it('renders approve and reject actions from backend-owned action fields', () => {
    const source = readSource();
    const helper = sourceSlice(
      source,
      'const hasBackendAllFreeAction = (request, action) => {',
      '/**'
    );

    expect(helper).toContain('request?.available_actions');
    expect(helper).toContain('ALL_FREE_ACTION_CAN_FIELD');
    expect(helper).toContain('return false;');

    const actionRendering = sourceSlice(
      source,
      '{(hasBackendAllFreeAction(request, \'approve\')',
      '{showApprovalModal && selectedRequest &&'
    );

    expect(actionRendering).toContain('hasBackendAllFreeAction(request, \'approve\')');
    expect(actionRendering).toContain('hasBackendAllFreeAction(request, \'reject\')');
    expect(actionRendering).not.toContain('request.approval_status === \'pending\'');
  });
});
