import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const sourcePath = path.resolve(
  process.cwd(),
  'src/components/admin/AllFreeApproval.tsx'
);

const readSource = () => fs.readFileSync(sourcePath, 'utf8');

const sourceSlice = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
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
