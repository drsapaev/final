import { describe, expect, it } from 'vitest';
import { mcpAPI } from '../mcp';

describe('local MCP fallback', () => {
  it('does not manufacture successful AI responses', async () => {
    const responses = await Promise.all([
      mcpAPI.chat({ messages: [{ content: 'synthetic' }] }),
      mcpAPI.generateSuggestions({ context: 'synthetic', type: 'medical' }),
      mcpAPI.translate({ text: 'synthetic' }),
      mcpAPI.analyzeImage(new Blob(), 'medical'),
    ]);
    for (const response of responses) {
      expect(response).toEqual({ status: 'error', error: 'AI service unavailable' });
    }
  });
});
