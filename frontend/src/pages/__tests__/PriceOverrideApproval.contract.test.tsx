import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const sourcePath = path.resolve(
  process.cwd(),
  'src/components/registrar/PriceOverrideApproval.tsx'
);

const readSource = () => fs.readFileSync(sourcePath, 'utf8');

const sourceSlice = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('PriceOverrideApproval action contract', () => {
  it('renders approve and reject actions from backend-owned action fields', () => {
    const source = readSource();
    const helper = sourceSlice(
      source,
      'const hasBackendPriceOverrideAction = (override, action) => {',
      '/**'
    );

    expect(helper).toContain('override?.available_actions');
    expect(helper).toContain('PRICE_OVERRIDE_ACTION_CAN_FIELD');
    expect(helper).toContain('return false;');

    const actionRendering = sourceSlice(
      source,
      '{(hasBackendPriceOverrideAction(override, \'approve\')',
      '{showApprovalModal && selectedOverride &&'
    );

    expect(actionRendering).toContain('hasBackendPriceOverrideAction(override, \'approve\')');
    expect(actionRendering).toContain('hasBackendPriceOverrideAction(override, \'reject\')');
    expect(actionRendering).not.toContain('override.status === \'pending\'');
  });
});
