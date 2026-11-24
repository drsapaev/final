import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ chat: vi.fn(), generateSuggestions: vi.fn(), translate: vi.fn(), analyzeImage: vi.fn() }));
vi.mock('../../utils/mcp', () => ({ mcpAPI: mocks }));
vi.mock('../useEnhancedMediaQuery', () => ({ useReducedMotion: () => false }));
import { useAIAssistant, useAISuggestions, useAITranslation, useAIImageAnalysis } from '../useAI';

const safe = { requires_doctor_confirmation: true };
const suggestion = { text: 'SYNTHETIC CLINICAL', confidence: 0.8, category: 'medical' };

describe('legacy AI hooks require server safety metadata', () => {
  beforeEach(() => { Object.values(mocks).forEach((mock) => mock.mockReset()); });

  it.each([undefined, null, {}, { requires_doctor_confirmation: false },
    { requires_doctor_confirmation: 1 }, { requires_doctor_confirmation: 'true' }])(
    'never publishes unmarked assistant response %j', async (ai_safety_meta) => {
      mocks.chat.mockResolvedValue({ status: 'success', ai_safety_meta, data: { message: 'SYNTHETIC CLINICAL' } });
      const { result } = renderHook(() => useAIAssistant());
      await act(async () => { await result.current.sendMessage('question'); });
      expect(result.current.messages.some((item) => item.content === 'SYNTHETIC CLINICAL')).toBe(false);
      expect(result.current.error).toBeTruthy();
    },
  );

  it('publishes an explicitly verified assistant response', async () => {
    mocks.chat.mockResolvedValue({ status: 'success', ai_safety_meta: safe, data: { message: 'SYNTHETIC CLINICAL' } });
    const { result } = renderHook(() => useAIAssistant());
    await act(async () => { await result.current.sendMessage('question'); });
    expect(result.current.messages.some((item) => item.content === 'SYNTHETIC CLINICAL')).toBe(true);
  });

  it('does not restore an in-flight assistant response after clearing the conversation', async () => {
    let resolveOld!: (value: unknown) => void;
    mocks.chat.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; }));
    const { result } = renderHook(() => useAIAssistant());
    let request!: Promise<unknown>;
    await act(async () => { request = result.current.sendMessage('question'); });
    act(() => result.current.clearMessages());
    await act(async () => {
      resolveOld({ status: 'success', ai_safety_meta: safe, data: { message: 'SYNTHETIC CLINICAL' } });
      await request;
    });
    expect(result.current.messages).toEqual([]);
    expect(result.current.loading).toBe(false);
  });

  it('does not publish or save unverified suggestions', async () => {
    mocks.generateSuggestions.mockResolvedValue({ status: 'success', data: { suggestions: [suggestion] } });
    const { result } = renderHook(() => useAISuggestions());
    await act(async () => { await result.current.generateSuggestions('clinical'); });
    expect(result.current.suggestions).toEqual([]);
    expect(result.current.history).toEqual([]);
    expect(result.current.error).toBeTruthy();
  });

  it('publishes suggestions only with a strict verified envelope', async () => {
    mocks.generateSuggestions.mockResolvedValue({ status: 'success', ai_safety_meta: safe, data: { suggestions: [suggestion] } });
    const { result } = renderHook(() => useAISuggestions());
    await act(async () => { await result.current.generateSuggestions('clinical'); });
    expect(result.current.suggestions[0]?.text).toBe(suggestion.text);
  });

  it('does not publish older verified suggestions after a newer unsafe request', async () => {
    let resolveOld!: (value: unknown) => void;
    mocks.generateSuggestions.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce({ status: 'success', data: { suggestions: [suggestion] } });
    const { result } = renderHook(() => useAISuggestions());
    let older!: Promise<unknown>;
    await act(async () => { older = result.current.generateSuggestions('old'); });
    await act(async () => { await result.current.generateSuggestions('new'); });
    await act(async () => {
      resolveOld({ status: 'success', ai_safety_meta: safe, data: { suggestions: [suggestion] } });
      await older;
    });
    expect(result.current.suggestions).toEqual([]);
    expect(result.current.history).toEqual([]);
  });

  it('does not return an unverified translation as a successful result', async () => {
    mocks.translate.mockResolvedValue({ status: 'success', data: { translation: 'UNVERIFIED' } });
    const { result } = renderHook(() => useAITranslation());
    await act(async () => { await expect(result.current.translate('original')).rejects.toThrow('AI translation unavailable'); });
    expect(result.current.translations).toEqual([]);
    expect(result.current.error).toBeTruthy();
    let batch: Awaited<ReturnType<typeof result.current.translateBatch>> = [];
    await act(async () => { batch = await result.current.translateBatch(['original']); });
    expect(batch).toEqual([{ original: 'original', translated: '', error: 'AI translation unavailable' }]);
  });

  it('returns a translation from an explicitly verified response', async () => {
    mocks.translate.mockResolvedValue({ status: 'success', ai_safety_meta: safe, data: { translation: 'SYNTHETIC TRANSLATION' } });
    const { result } = renderHook(() => useAITranslation());
    await act(async () => { await expect(result.current.translate('original')).resolves.toBe('SYNTHETIC TRANSLATION'); });
    expect(result.current.translations[0]?.translated).toBe('SYNTHETIC TRANSLATION');
  });

  it('rejects an unverified image response', async () => {
    mocks.analyzeImage.mockResolvedValue({ status: 'success', data: { summary: 'UNVERIFIED' } });
    const { result } = renderHook(() => useAIImageAnalysis());
    await act(async () => { await expect(result.current.analyzeMedicalImage(new Blob())).rejects.toThrow(); });
    expect(result.current.analysis).toBeNull();
  });

  it('allows image data from a verified response', async () => {
    mocks.analyzeImage.mockResolvedValue({ status: 'success', ai_safety_meta: safe, data: { summary: 'SYNTHETIC' } });
    const { result } = renderHook(() => useAIImageAnalysis());
    await act(async () => { await expect(result.current.analyzeMedicalImage(new Blob())).resolves.toEqual({ summary: 'SYNTHETIC' }); });
  });

  it('does not allow the public analysis setter to bypass the safety check', () => {
    const { result } = renderHook(() => useAIImageAnalysis());
    expect(() => act(() => result.current.setAnalysis({ summary: 'UNVERIFIED' }))).toThrow();
    expect(result.current.analysis).toBeNull();
    act(() => result.current.setAnalysis({ ai_safety_meta: safe, data: { summary: 'SYNTHETIC' } }));
    expect(result.current.analysis).toEqual({ ai_safety_meta: safe, data: { summary: 'SYNTHETIC' } });
    act(() => result.current.setAnalysis(null));
    expect(result.current.analysis).toBeNull();
    act(() => result.current.setAnalysis({ ai_safety_meta: safe, data: { summary: 'SYNTHETIC' } }));
    act(() => result.current.clearResults());
    expect(result.current.analysis).toBeNull();
  });
});
