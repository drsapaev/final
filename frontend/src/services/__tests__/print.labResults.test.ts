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

  it('a transport error is a KNOWN failure', async () => {
    mockedPost.mockRejectedValueOnce(new Error('network down'));
    const result = await printService.printLabResults({ report_instance_id: 5 });
    expect(result.success).toBe(false);
    expect((result as { ambiguous?: boolean }).ambiguous).toBe(false);
    expect((result as { error?: unknown }).error).toBe('network down');
  });
});
