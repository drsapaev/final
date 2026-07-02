/**
 * Unit tests for MCP Client
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import axios from 'axios';

vi.mock('axios', () => {
  const defaultClient = {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() }
    }
  };

  return {
    default: {
      create: vi.fn(() => defaultClient)
    }
  };
});

describe('MCP Client API', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  describe('analyzeComplaint', () => {
    it('should successfully analyze a complaint', async () => {
      const mockResponse = {
        data: {
          status: 'success',
          data: {
            preliminary_diagnosis: ['Мигрень'],
            examinations: [],
            lab_tests: [],
            urgency: 'планово'
          }
        }
      };

      const mockClient = {
        post: vi.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() }
        }
      };
      axios.create.mockReturnValue(mockClient);
      const { mcpAPI } = await import('../mcpClient');

      const result = await mcpAPI.analyzeComplaint({
        complaint: 'Головная боль',
        patientAge: 30,
        patientGender: 'female',
        provider: 'deepseek'
      });

      expect(result.status).toBe('success');
      expect(result.data.preliminary_diagnosis).toContain('Мигрень');
    });

    it('should handle errors gracefully', async () => {
      const mockClient = {
        post: vi.fn().mockRejectedValue(new Error('Network error')),
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() }
        }
      };
      axios.create.mockReturnValue(mockClient);
      const { mcpAPI } = await import('../mcpClient');

      await expect(
        mcpAPI.analyzeComplaint({
          complaint: 'Test',
          patientAge: 30,
          patientGender: 'male'
        })
      ).rejects.toThrow('Network error');
    });
  });

  describe('suggestICD10', () => {
    it('should return ICD10 suggestions', async () => {
      const mockResponse = {
        data: {
          status: 'success',
          data: {
            suggestions: [
              { code: 'G43.9', name: 'Мигрень неуточненная', relevance: 'высокая' }
            ],
            clinical_recommendations: 'Клинические рекомендации...'
          }
        }
      };

      const mockClient = {
        post: vi.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() }
        }
      };
      axios.create.mockReturnValue(mockClient);
      const { mcpAPI } = await import('../mcpClient');

      const result = await mcpAPI.suggestICD10({
        symptoms: ['головная боль'],
        diagnosis: 'мигрень',
        provider: 'deepseek'
      });

      expect(result.status).toBe('success');
      expect(result.data.suggestions).toHaveLength(1);
      expect(result.data.suggestions[0].code).toBe('G43.9');
    });
  });

  describe('interpretLabResults', () => {
    it('should interpret lab results', async () => {
      const mockResponse = {
        data: {
          status: 'success',
          data: {
            summary: 'Результаты в пределах нормы',
            abnormal_values: [],
            recommendations: []
          }
        }
      };

      const mockClient = {
        post: vi.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() }
        }
      };
      axios.create.mockReturnValue(mockClient);
      const { mcpAPI } = await import('../mcpClient');

      const result = await mcpAPI.interpretLabResults({
        results: [
          { parameter: 'Гемоглобин', value: 140, unit: 'г/л' }
        ],
        patientAge: 30,
        patientGender: 'male',
        provider: 'deepseek'
      });

      expect(result.status).toBe('success');
      expect(result.data.summary).toBeDefined();
    });
  });

  describe('analyzeSkinLesion', () => {
    it('should analyze skin lesion image', async () => {
      const mockFile = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
      const mockResponse = {
        data: {
          status: 'success',
          data: {
            findings: 'Обнаружено доброкачественное образование',
            recommendations: ['Наблюдение']
          }
        }
      };

      const mockClient = {
        post: vi.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() }
        }
      };
      axios.create.mockReturnValue(mockClient);
      const { mcpAPI } = await import('../mcpClient');

      const result = await mcpAPI.analyzeSkinLesion(
        mockFile,
        { location: 'рука', size: '1см' },
        null,
        'deepseek'
      );

      expect(result.status).toBe('success');
      expect(result.data.findings).toBeDefined();
    });
  });

  describe('getStatus', () => {
    it('should get MCP system status', async () => {
      const mockResponse = {
        data: {
          status: 'healthy',
          servers: ['complaint', 'icd10', 'lab', 'imaging']
        }
      };

      const mockClient = {
        get: vi.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() }
        }
      };
      axios.create.mockReturnValue(mockClient);
      const { mcpAPI } = await import('../mcpClient');

      const result = await mcpAPI.getStatus();

      expect(result.status).toBe('healthy');
      expect(result.servers).toContain('complaint');
    });
  });
});

