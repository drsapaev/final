/**
 * Unit tests for MCP Client
 */
import { mcpAPI } from '../mcpClient';
import axios from 'axios';

// Mock axios
jest.mock('axios');

describe('MCP Client API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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

      axios.create.mockReturnValue({
        post: jest.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: jest.fn() },
          response: { use: jest.fn() }
        }
      });

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
      axios.create.mockReturnValue({
        post: jest.fn().mockRejectedValue(new Error('Network error')),
        interceptors: {
          request: { use: jest.fn() },
          response: { use: jest.fn() }
        }
      });

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

      axios.create.mockReturnValue({
        post: jest.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: jest.fn() },
          response: { use: jest.fn() }
        }
      });

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

      axios.create.mockReturnValue({
        post: jest.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: jest.fn() },
          response: { use: jest.fn() }
        }
      });

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

      axios.create.mockReturnValue({
        post: jest.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: jest.fn() },
          response: { use: jest.fn() }
        }
      });

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

      axios.create.mockReturnValue({
        get: jest.fn().mockResolvedValue(mockResponse),
        interceptors: {
          request: { use: jest.fn() },
          response: { use: jest.fn() }
        }
      });

      const result = await mcpAPI.getStatus();

      expect(result.status).toBe('healthy');
      expect(result.servers).toContain('complaint');
    });
  });
});

