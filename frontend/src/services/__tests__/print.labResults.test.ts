import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * LABPRINT-FE-003 (audit 3886, round 14) — fail-first.
 *
 * Старый printLabResults признавал успехом ЛЮБОЙ 2xx без явного
 * success:false (normalizePrintResponse: «non-false»): {}/{success:null}
 * синтезировали подтверждение, и UI мог помечать отчёт PRINTED без
 * подтверждённого задания печати. Теперь: успех только при
 * success === true; 2xx без положительного ACK — честный ambiguous
 * (задание могло встать в очередь — никакого слепого повтора).
 * Плюс LABPRINT-FE-001: команда печати — только report_instance_id.
 */

vi.mock('../../api/client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { api } from '../../api/client';
import { printService } from '../print';

const mockedPost = api.post as unknown as ReturnType<typeof vi.fn>;

describe('LABPRINT-FE-003: printLabResults strict ACK', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends ONLY the report_instance_id (LABPRINT-FE-001)', async () => {
    mockedPost.mockResolvedValueOnce({ data: { success: true, job_id: 5, message: 'ok', printer: 'A4' } });
    await printService.printLabResults({ report_instance_id: 5, printer_name: null });
    expect(mockedPost).toHaveBeenCalledWith('/print/lab-results', {
      report_instance_id: 5,
      printer_name: null,
    });
  });

  it('a positive ACK with job receipt is a confirmed success', async () => {
    mockedPost.mockResolvedValueOnce({ data: { success: true, job_id: 5, message: 'ok', printer: 'A4' } });
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(true);
    expect((result as { data?: { job_id?: number } }).data?.job_id).toBe(5);
  });

  it('2xx with an EMPTY object is ambiguous, not success (was synthesized true)', async () => {
    mockedPost.mockResolvedValueOnce({ data: {} });
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(true);
  });

  it('2xx with success:null is ambiguous, not success', async () => {
    mockedPost.mockResolvedValueOnce({ data: { success: null } });
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(true);
  });

  it('2xx with a non-contract status payload is ambiguous', async () => {
    mockedPost.mockResolvedValueOnce({ data: { status: 'queued' } });
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(true);
  });

  it('an explicit success:false is a KNOWN failure, not ambiguous', async () => {
    mockedPost.mockResolvedValueOnce({ data: { success: false, error: 'no printer attached' } });
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(false);
    expect((result as { error?: string }).error).toBe('no printer attached');
  });

  // ── RETRO-3921-01 (consolidated post-merge review of #3921, PR #3944) ──
  // The old contract treated EVERY rejection as a definite failure
  // (ambiguous:false), so a client timeout / dropped connection AFTER the
  // server had accepted and queued the job fell through to the automatic
  // PDF fallback — a second print route for a job that may already be
  // queued. Only a server-RETURNED error is a definite refusal; a missing
  // transport result is an UNKNOWN outcome (ambiguous) and must stop the
  // fallback.

  it('RETRO-3921-01: a client timeout after the server may have queued the job is AMBIGUOUS', async () => {
    const timeoutError = Object.assign(new Error('timeout of 15000ms exceeded'), {
      code: 'ECONNABORTED',
    });
    mockedPost.mockRejectedValueOnce(timeoutError);
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(true);
  });

  it('RETRO-3921-01: a dropped connection (no server response) is AMBIGUOUS, not a definite failure', async () => {
    const networkError = Object.assign(new Error('Network Error'), {
      code: 'ERR_NETWORK',
    });
    mockedPost.mockRejectedValueOnce(networkError);
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(true);
  });

  it('RETRO-3921-01: an aborted request has an UNKNOWN outcome — AMBIGUOUS', async () => {
    const canceledError = Object.assign(new Error('canceled'), {
      code: 'ERR_CANCELED',
    });
    mockedPost.mockRejectedValueOnce(canceledError);
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(true);
  });

  it('RETRO-3921-01: a server-RETURNED error status is a definite failure (fallback stays allowed)', async () => {
    mockedPost.mockRejectedValueOnce({
      response: { status: 503, data: { detail: 'print service unavailable' } },
    });
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    // The server answered: the job was NOT queued — the operator-driven
    // PDF fallback may proceed.
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(false);
  });
});
