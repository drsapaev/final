import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');
// PR-UI-14-6: RefundRequestsTable decomposed (behavior-preserving) —
// contracts/guards -> refundRequestsContracts.ts; data lifecycle + process
// commands -> useRefundRequests.ts; badges/actions/columns ->
// refundRequestsColumns.tsx; the table keeps only composition + JSX.
const readSource = (rel: string) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

const contractsSource = readSource('components/cashier/refundRequestsContracts.ts');
const hookSource = readSource('components/cashier/useRefundRequests.ts');
const columnsSource = readSource('components/cashier/refundRequestsColumns.tsx');

describe('RefundRequestsTable command contract', () => {
  it('uses the published refund request list filter query name', () => {
    expect(hookSource).toContain('params.status_filter = filter');
    expect(hookSource).not.toContain('params.append(\'status\', filter)');
  });

  it('routes list and process commands through the shared api client (CSH-FE-011/012)', () => {
    // canonical transport: shared axios instance with /api/v1 base URL,
    // Bearer, CSRF on POST, 401 refresh and 429 cooldown
    expect(hookSource).toContain('from \'../../api/client\'');
    expect(hookSource).toContain('api.get(\'/force-majeure/refund-requests\'');
    expect(hookSource).toContain('api.post(`/force-majeure/refund-requests/${requestId}/process`');

    // no raw fetch() anywhere in the hook — the origin-relative URL without
    // /api/v1 and the headerless POST were the CSH-FE-011/012 defects
    expect(hookSource).not.toContain('fetch(');
    expect(hookSource).not.toContain('tokenManager');
    expect(hookSource).not.toContain('\'Authorization\'');
  });

  it('uses the existing backend process command instead of invented action URLs', () => {
    expect(hookSource).toContain('api.post(`/force-majeure/refund-requests/${requestId}/process`');
    expect(hookSource).toContain('{\n        action,\n        ...extraPayload,\n      }');

    expect(hookSource).not.toContain('/force-majeure/refund-requests/${requestId}/approve');
    expect(hookSource).not.toContain('/force-majeure/refund-requests/${requestId}/reject');
    expect(hookSource).not.toContain('/force-majeure/refund-requests/${requestId}/complete');
  });

  it('renders refund commands only from backend-provided availability', () => {
    expect(contractsSource).toContain('const hasBackendRefundAction =');
    expect(columnsSource).toContain('hasBackendRefundAction(request, \'approve\')');
    expect(columnsSource).toContain('hasBackendRefundAction(request, \'reject\')');
    expect(columnsSource).toContain('hasBackendRefundAction(request, \'complete\')');

    // PR-UI-14-6 marker fix: the original test pinned
    // 'const renderActions = (request) => {' which never matched the real
    // typed signature '(request: RefundRequest) => {' — the block slice was
    // vacuously empty and the not.toContain assertions below never really
    // asserted anything. Corrected marker makes the pin real.
    const renderActionsStart = columnsSource.indexOf('const renderActions = (request: RefundRequest) => {');
    const renderActionsEnd = columnsSource.indexOf('return [', renderActionsStart);
    expect(renderActionsStart).toBeGreaterThanOrEqual(0);
    expect(renderActionsEnd).toBeGreaterThan(renderActionsStart);
    const renderActionsBlock = columnsSource.slice(renderActionsStart, renderActionsEnd);

    expect(renderActionsBlock).not.toContain('request.status === \'pending\'');
    expect(renderActionsBlock).not.toContain('request.status === \'approved\'');
  });
});
