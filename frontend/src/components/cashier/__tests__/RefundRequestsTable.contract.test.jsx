import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');
const source = fs.readFileSync(path.join(ROOT, 'components/cashier/RefundRequestsTable.tsx'), 'utf8');

describe('RefundRequestsTable command contract', () => {
  it('uses the published refund request list filter query name', () => {
    expect(source).toContain('params.append(\'status_filter\', filter)');
    expect(source).not.toContain('params.append(\'status\', filter)');
  });

  it('uses the existing backend process command instead of invented action URLs', () => {
    expect(source).toContain('/force-majeure/refund-requests/${requestId}/process');
    expect(source).toContain('body: JSON.stringify({ action, ...extraPayload })');

    expect(source).not.toContain('/force-majeure/refund-requests/${requestId}/approve');
    expect(source).not.toContain('/force-majeure/refund-requests/${requestId}/reject');
    expect(source).not.toContain('/force-majeure/refund-requests/${requestId}/complete');
  });

  it('renders refund commands only from backend-provided availability', () => {
    expect(source).toContain('const hasBackendRefundAction =');
    expect(source).toContain('hasBackendRefundAction(request, \'approve\')');
    expect(source).toContain('hasBackendRefundAction(request, \'reject\')');
    expect(source).toContain('hasBackendRefundAction(request, \'complete\')');

    const renderActionsBlock = source.slice(
      source.indexOf('const renderActions = (request) => {'),
      source.indexOf('const columns = [')
    );

    expect(renderActionsBlock).not.toContain('request.status === \'pending\'');
    expect(renderActionsBlock).not.toContain('request.status === \'approved\'');
  });
});
