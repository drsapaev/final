import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { normalizeSource } from '../../test/contracts/source-contract-helper';

const sourcePath = path.resolve(
  process.cwd(),
  'src/components/registrar/PriceOverrideApproval.tsx'
);

const readSource = () => normalizeSource(fs.readFileSync(sourcePath, 'utf8'));

const sourceSlice = (source: string, startMarker: string, endMarker: string) => {
  const start = source.indexOf(normalizeSource(startMarker));
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(normalizeSource(endMarker), start);
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

    // Contract: approve/reject actions are gated by hasBackendPriceOverrideAction,
    // NOT by legacy `override.status === 'pending'`. Assertions check the whole source
    // (no slice) — the architectural contract is the gating predicate itself, not the
    // surrounding JSX form. Survives TS strict-mode narrowing (e.g., `&&` → `!= null &&`)
    // and any modal boundary refactor.
    expect(source).toContain('hasBackendPriceOverrideAction(override, \'approve\')');
    expect(source).toContain('hasBackendPriceOverrideAction(override, \'reject\')');
    expect(source).not.toContain('override.status === \'pending\'');
  });
});
