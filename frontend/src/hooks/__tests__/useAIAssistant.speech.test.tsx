import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { chatMock } = vi.hoisted(() => ({
  chatMock: vi.fn(),
}));

vi.mock('../../utils/mcp', () => ({
  mcpAPI: { chat: chatMock },
}));

vi.mock('../../utils/aiValidator', () => ({
  detectPromptInjection: vi.fn(() => false),
  validateAIChatMessage: vi.fn((message) => message),
}));

vi.mock('../useEnhancedMediaQuery', () => ({
  useReducedMotion: vi.fn(),
}));

import { useAIAssistant } from '../useAI';

describe('useAIAssistant speech recognition', () => {
  let recognition: {
    onresult: ((event: Event) => void) | null;
    start: ReturnType<typeof vi.fn>;
    stop: ReturnType<typeof vi.fn>;
    abort: ReturnType<typeof vi.fn>;
    onerror: ((event: Event) => void) | null;
    onend: (() => void) | null;
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    maxAlternatives: number;
  };

  beforeEach(() => {
    chatMock.mockReset();
    chatMock.mockResolvedValue({
      status: 'success',
      data: {
        message: 'Synthetic assistant response',
        metadata: { ai_safety_meta: { requires_doctor_confirmation: true } },
      },
    });

    recognition = {
      onresult: null,
      onerror: null,
      onend: null,
      start: vi.fn(),
      stop: vi.fn(),
      abort: vi.fn(),
      continuous: false,
      interimResults: false,
      lang: '',
      maxAlternatives: 1,
    };

    Object.defineProperty(window, 'SpeechRecognition', {
      configurable: true,
      value: function SpeechRecognition() {
        return recognition;
      },
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(window, 'SpeechRecognition');
  });

  it('sends the first alternative transcript to the assistant', async () => {
    const { result } = renderHook(() => useAIAssistant());

    act(() => result.current.startListening());
    expect(recognition.start).toHaveBeenCalledOnce();

    const alternative = { transcript: 'recognized synthetic words', confidence: 1 };
    const speechResult = Object.assign([alternative], {
      item: () => alternative,
    });
    const speechResults = Object.assign([speechResult], {
      item: () => speechResult,
    });
    const event = { resultIndex: 0, results: speechResults } as unknown as Event;

    act(() => recognition.onresult?.(event));

    await waitFor(() => expect(chatMock).toHaveBeenCalledOnce());
    const payload = chatMock.mock.calls[0]?.[0] as {
      messages: Array<{ content: string }>;
    };
    expect(payload.messages[payload.messages.length - 1]?.content).toBe(
      'recognized synthetic words',
    );
  });
});
