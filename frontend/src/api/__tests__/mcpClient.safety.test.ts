import { beforeEach, describe, expect, it, vi } from 'vitest';

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../client', () => ({ api: http }));
vi.mock('../../utils/navigation', () => ({ hardRedirectToLogin: vi.fn() }));
vi.mock('../../utils/logger', () => ({ default: { error: vi.fn() } }));
import { mcpAPI } from '../mcpClient';

const calls = [
  () => mcpAPI.analyzeComplaint({ complaint: 'SYNTHETIC' }),
  () => mcpAPI.validateComplaint('SYNTHETIC'),
  () => mcpAPI.suggestICD10({ symptoms: ['SYNTHETIC'] }),
  () => mcpAPI.validateICD10('SYNTHETIC'),
  () => mcpAPI.interpretLabResults({ results: [] }),
  () => mcpAPI.checkCriticalValues({}),
  () => mcpAPI.analyzeImage(new Blob(['synthetic']), 'general'),
  () => mcpAPI.analyzeSkinLesion(new Blob(['synthetic'])),
  () => mcpAPI.batchProcess([]),
];

describe('MCP medical response boundary', () => {
  beforeEach(() => vi.clearAllMocks());

  it.each(calls)('requires a nested safety marker before returning medical content', async (call) => {
    http.post.mockResolvedValue({ data: { status: 'success', data: ['SYNTHETIC'] } });
    await expect(call()).rejects.toThrow('safety confirmation');
    const safe = { status: 'success', data: ['SYNTHETIC'], ai_safety_meta: { requires_doctor_confirmation: true } };
    http.post.mockResolvedValue({ data: safe });
    await expect(call()).resolves.toEqual(safe);
  });

  it.each([false, 1, 'true', null])('rejects a non-boolean-true marker: %j', async (marker) => {
    http.post.mockResolvedValue({ data: { status: 'success', ai_safety_meta: { requires_doctor_confirmation: marker } } });
    await expect(mcpAPI.analyzeComplaint({})).rejects.toThrow('safety confirmation');
  });

  it('preserves unmarked health and reference responses', async () => {
    http.get.mockResolvedValue({ data: { status: 'healthy' } });
    await expect(mcpAPI.healthCheck()).resolves.toEqual({ status: 'healthy' });
    await expect(mcpAPI.searchICD10('SYNTHETIC')).resolves.toEqual({ status: 'healthy' });
  });
});
