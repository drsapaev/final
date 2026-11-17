import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ post: vi.fn(), suggestICD10: vi.fn() }));
vi.mock('../../api/client', () => ({ api: { post: mocks.post } }));
vi.mock('../../api/mcpClient', () => ({ mcpAPI: { suggestICD10: mocks.suggestICD10 } }));
import { useEMRAI } from '../useEMRAI';

const suggestion = { code: 'A01', description: 'Synthetic', confidence: 0.8 };
const marker = { requires_doctor_confirmation: true };

describe('medical AI safety at EMR hook boundary', () => {
  beforeEach(() => { mocks.post.mockReset(); mocks.suggestICD10.mockReset(); });

  it.each([undefined, null, {}, { requires_doctor_confirmation: false },
    { requires_doctor_confirmation: 1 }, { requires_doctor_confirmation: 'true' }])(
    'does not publish legacy ICD response with invalid nested metadata %j', async (ai_safety_meta) => {
      mocks.post.mockResolvedValue({ data: { data: [suggestion], ai_safety_meta } });
      const { result } = renderHook(() => useEMRAI(false));
      await act(async () => { await result.current.getICD10Suggestions('symptom', 'diagnosis'); });
      expect(result.current.icd10Suggestions).toEqual([]);
      expect(result.current.error).toBeTruthy();
    },
  );

  it('unwraps a valid legacy ICD envelope only after checking it', async () => {
    mocks.post.mockResolvedValue({ data: { data: [suggestion], ai_safety_meta: marker } });
    const { result } = renderHook(() => useEMRAI(false));
    await act(async () => { await result.current.getICD10Suggestions('symptom', 'diagnosis'); });
    expect(result.current.icd10Suggestions).toHaveLength(1);
  });

  it('preserves the real legacy provider ICD shape and fields', async () => {
    const legacy = { code: 'A01', name: 'Synthetic diagnosis', relevance: 0.8 };
    mocks.post.mockResolvedValue({ data: { data: [legacy], ai_safety_meta: marker } });
    const { result } = renderHook(() => useEMRAI(false, 'mock'));
    await act(async () => { await result.current.getICD10Suggestions('symptom', 'diagnosis'); });
    expect(result.current.icd10Suggestions).toEqual([legacy]);
  });

  it('rejects an unsafe MCP response even if the client is replaced or mocked', async () => {
    mocks.suggestICD10.mockResolvedValue({ status: 'success', data: { suggestions: [suggestion] } });
    const { result } = renderHook(() => useEMRAI(true));
    await act(async () => { await result.current.getICD10Suggestions('symptom', 'diagnosis'); });
    expect(result.current.icd10Suggestions).toEqual([]);
  });

  it('does not restore an older safe result after a newer unsafe response', async () => {
    let resolveOld!: (value: unknown) => void;
    const oldResponse = new Promise((resolve) => { resolveOld = resolve; });
    mocks.post.mockReturnValueOnce(oldResponse).mockResolvedValueOnce({ data: { data: [suggestion] } });
    const { result } = renderHook(() => useEMRAI(false));
    let older!: Promise<unknown>;
    await act(async () => { older = result.current.getICD10Suggestions('old', 'diagnosis')!; });
    await act(async () => { await result.current.getICD10Suggestions('new', 'diagnosis'); });
    expect(result.current.icd10Suggestions).toEqual([]);
    expect(result.current.error).toBeTruthy();
    await act(async () => {
      resolveOld({ data: { data: [suggestion], ai_safety_meta: marker } });
      await older;
    });
    expect(result.current.icd10Suggestions).toEqual([]);
    expect(result.current.loading).toBe(false);
  });

  it('does not return a clinical suggestion after the hook unmounts', async () => {
    let resolveOld!: (value: unknown) => void;
    mocks.post.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; }));
    const { result, unmount } = renderHook(() => useEMRAI(false));
    let request!: Promise<unknown>;
    await act(async () => { request = result.current.getICD10Suggestions('symptom', 'diagnosis')!; });
    unmount();
    resolveOld({ data: { data: [suggestion], ai_safety_meta: marker } });
    await expect(request).resolves.toEqual([]);
  });

  it('clears all verified ICD results without exposing raw clinical state setters', async () => {
    mocks.suggestICD10.mockResolvedValue({
      status: 'success', ai_safety_meta: marker,
      data: { suggestions: [suggestion], clinical_recommendations: { red_flags: ['synthetic'] } },
    });
    const { result } = renderHook(() => useEMRAI(true));
    await act(async () => { await result.current.getICD10Suggestions('symptom', 'diagnosis'); });
    expect(result.current.icd10Suggestions).toHaveLength(1);
    expect(result.current.clinicalRecommendations?.red_flags).toEqual(['synthetic']);
    expect('setIcd10Suggestions' in result.current).toBe(false);
    expect('setClinicalRecommendations' in result.current).toBe(false);
    act(() => { result.current.clearSuggestions(); });
    expect(result.current.icd10Suggestions).toEqual([]);
    expect(result.current.clinicalRecommendations).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('keeps suggestions and recommendations empty after clearing an in-flight request', async () => {
    let resolvePending!: (value: unknown) => void;
    mocks.suggestICD10.mockReturnValueOnce(new Promise((resolve) => { resolvePending = resolve; }));
    const { result } = renderHook(() => useEMRAI(true));
    let request!: Promise<unknown>;
    await act(async () => { request = result.current.getICD10Suggestions('symptom', 'diagnosis')!; });
    expect(result.current.loading).toBe(true);
    act(() => { result.current.clearSuggestions(); });
    expect(result.current.loading).toBe(false);
    await act(async () => {
      resolvePending({
        status: 'success', ai_safety_meta: marker,
        data: { suggestions: [suggestion], clinical_recommendations: { red_flags: ['synthetic'] } },
      });
      await expect(request).resolves.toEqual([]);
    });
    expect(result.current.icd10Suggestions).toEqual([]);
    expect(result.current.clinicalRecommendations).toBeNull();
  });

  it('can request fresh verified suggestions after clearing', async () => {
    mocks.post.mockResolvedValue({ data: { data: [suggestion], ai_safety_meta: marker } });
    const { result } = renderHook(() => useEMRAI(false));
    act(() => { result.current.clearSuggestions(); });
    await act(async () => { await result.current.getICD10Suggestions('symptom', 'diagnosis'); });
    expect(result.current.icd10Suggestions).toEqual([suggestion]);
  });
});
