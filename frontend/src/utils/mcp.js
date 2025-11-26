// Safe MCP fallback API used by useAI.jsx
// Provides stubbed methods to avoid runtime failures when MCP backend is absent

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const success = (data) => ({ status: 'success', data });
const failure = (error) => ({ status: 'error', error: String(error || 'Unavailable') });

export const mcpAPI = {
  async chat({ messages = [], provider = 'mcp', model = 'gpt-4' } = {}) {
    try {
      await delay(50);
      const last = messages[messages.length - 1];
      return success({
        message: last?.content ? `Echo (${provider}/${model}): ${last.content}` : 'Здравствуйте! Чем могу помочь?',
        metadata: { provider, model, stub: true }
      });
    } catch (e) {
      return failure(e);
    }
  },

  async generateSuggestions({ context = '', type = 'medical', maxSuggestions = 5 } = {}) {
    try {
      await delay(50);
      const suggestions = Array.from({ length: Math.max(1, Math.min(maxSuggestions, 5)) }).map((_, i) => ({
        text: `Предложение ${i + 1} для контекста: ${context}`,
        confidence: 0.6 + i * 0.05,
        category: type
      }));
      return success({ suggestions, metadata: { type, stub: true } });
    } catch (e) {
      return failure(e);
    }
  },

  async translate({ text = '', from = 'ru', to = 'en' } = {}) {
    try {
      await delay(50);
      // Simple mock translation by marking text
      return success({ translation: `[${from}->${to}] ${text}`, metadata: { stub: true } });
    } catch (e) {
      return failure(e);
    }
  },

  async analyzeImage(_file, imageType = 'general', _options = {}) {
    try {
      await delay(50);
      return success({
        summary: `Анализ изображения (${imageType}) выполнен (stub)`,
        findings: [],
        metadata: { stub: true }
      });
    } catch (e) {
      return failure(e);
    }
  }
};

export default mcpAPI;


