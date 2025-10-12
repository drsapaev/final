/**
 * Unit tests for AIAssistant component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SnackbarProvider } from 'notistack';
import AIAssistant from '../AIAssistant';
import { mcpAPI } from '../../../api/mcpClient';

// Mock MCP API
jest.mock('../../../api/mcpClient', () => ({
  mcpAPI: {
    analyzeComplaint: jest.fn(),
    suggestICD10: jest.fn(),
    interpretLabResults: jest.fn(),
    analyzeSkinLesion: jest.fn(),
    analyzeImage: jest.fn()
  }
}));

const MockWrapper = ({ children }) => (
  <SnackbarProvider maxSnack={3}>
    {children}
  </SnackbarProvider>
);

describe('AIAssistant Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Complaint Analysis', () => {
    it('should render complaint analysis assistant', () => {
      render(
        <MockWrapper>
          <AIAssistant
            analysisType="complaint"
            data={{
              complaint: 'Головная боль',
              patient_age: 30,
              patient_gender: 'female'
            }}
            title="Анализ жалоб"
            useMCP={true}
          />
        </MockWrapper>
      );

      expect(screen.getByText('Анализ жалоб')).toBeInTheDocument();
      expect(screen.getByText('MCP')).toBeInTheDocument();
    });

    it('should analyze complaint on refresh button click', async () => {
      const mockResult = {
        status: 'success',
        data: {
          preliminary_diagnosis: ['Мигрень', 'Головная боль напряжения'],
          examinations: [
            {
              type: 'Неврологический осмотр',
              name: 'Оценка неврологического статуса',
              reason: 'Выявление очаговой симптоматики'
            }
          ],
          lab_tests: ['Общий анализ крови'],
          urgency: 'планово'
        }
      };

      mcpAPI.analyzeComplaint.mockResolvedValue(mockResult);

      render(
        <MockWrapper>
          <AIAssistant
            analysisType="complaint"
            data={{
              complaint: 'Головная боль',
              patient_age: 30,
              patient_gender: 'female'
            }}
            useMCP={true}
          />
        </MockWrapper>
      );

      const refreshButton = screen.getByRole('button', { name: /повторить анализ/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mcpAPI.analyzeComplaint).toHaveBeenCalledWith({
          complaint: 'Головная боль',
          patientAge: 30,
          patientGender: 'female',
          provider: 'deepseek'
        });
      });

      await waitFor(() => {
        expect(screen.getByText('Мигрень')).toBeInTheDocument();
      });
    });
  });

  describe('ICD10 Suggestions', () => {
    it('should fetch ICD10 suggestions', async () => {
      const mockResult = {
        status: 'success',
        data: {
          suggestions: [
            { code: 'G43.9', name: 'Мигрень неуточненная', relevance: 'высокая' },
            { code: 'G44.2', name: 'Головная боль напряжения', relevance: 'средняя' }
          ],
          clinical_recommendations: 'Клинические рекомендации...'
        }
      };

      mcpAPI.suggestICD10.mockResolvedValue(mockResult);

      render(
        <MockWrapper>
          <AIAssistant
            analysisType="icd10"
            data={{
              symptoms: ['головная боль'],
              diagnosis: 'мигрень'
            }}
            useMCP={true}
          />
        </MockWrapper>
      );

      const refreshButton = screen.getByRole('button', { name: /повторить анализ/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mcpAPI.suggestICD10).toHaveBeenCalledWith({
          symptoms: ['головная боль'],
          diagnosis: 'мигрень',
          specialty: undefined,
          provider: 'deepseek',
          maxSuggestions: 5
        });
      });

      await waitFor(() => {
        expect(screen.getByText(/G43.9/)).toBeInTheDocument();
      });
    });

    it('should display clinical recommendations for ICD10', async () => {
      const mockResult = {
        status: 'success',
        data: {
          suggestions: [],
          clinical_recommendations: '### Клинические рекомендации\n\nДетальное описание...'
        }
      };

      mcpAPI.suggestICD10.mockResolvedValue(mockResult);

      render(
        <MockWrapper>
          <AIAssistant
            analysisType="icd10"
            data={{
              symptoms: [],
              diagnosis: 'снижение либидо'
            }}
            useMCP={true}
          />
        </MockWrapper>
      );

      const refreshButton = screen.getByRole('button', { name: /повторить анализ/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(screen.getByText(/Клинические рекомендации/)).toBeInTheDocument();
      });
    });
  });

  describe('Provider Selection', () => {
    it('should allow provider selection', () => {
      render(
        <MockWrapper>
          <AIAssistant
            analysisType="complaint"
            data={{ complaint: 'Test' }}
            providerOptions={['deepseek', 'gemini', 'openai']}
            useMCP={true}
          />
        </MockWrapper>
      );

      expect(screen.getByText('DEEPSEEK')).toBeInTheDocument();
      expect(screen.getByText('GEMINI')).toBeInTheDocument();
      expect(screen.getByText('OPENAI')).toBeInTheDocument();
    });

    it('should change provider on chip click', () => {
      render(
        <MockWrapper>
          <AIAssistant
            analysisType="complaint"
            data={{ complaint: 'Test' }}
            providerOptions={['deepseek', 'gemini']}
            useMCP={true}
          />
        </MockWrapper>
      );

      const geminiChip = screen.getByText('GEMINI');
      fireEvent.click(geminiChip);

      // Provider chip should be highlighted after click
      expect(geminiChip.closest('.MuiChip-root')).toHaveClass('MuiChip-filled');
    });
  });

  describe('Error Handling', () => {
    it('should display error message on API failure', async () => {
      mcpAPI.analyzeComplaint.mockRejectedValue(new Error('API Error'));

      render(
        <MockWrapper>
          <AIAssistant
            analysisType="complaint"
            data={{ complaint: 'Test' }}
            useMCP={true}
          />
        </MockWrapper>
      );

      const refreshButton = screen.getByRole('button', { name: /повторить анализ/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(screen.getByText(/API Error/)).toBeInTheDocument();
      });
    });

    it('should show retry suggestion after error', async () => {
      mcpAPI.analyzeComplaint.mockRejectedValue(new Error('Timeout'));

      render(
        <MockWrapper>
          <AIAssistant
            analysisType="complaint"
            data={{ complaint: 'Test' }}
            useMCP={true}
          />
        </MockWrapper>
      );

      const refreshButton = screen.getByRole('button', { name: /повторить анализ/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(screen.getByText(/Попытка 1/)).toBeInTheDocument();
      });
    });
  });

  describe('Lab Results Interpretation', () => {
    it('should interpret lab results via MCP', async () => {
      const mockResult = {
        status: 'success',
        data: {
          summary: 'Результаты в пределах нормы',
          abnormal_values: [],
          recommendations: ['Контроль через 6 месяцев']
        }
      };

      mcpAPI.interpretLabResults.mockResolvedValue(mockResult);

      render(
        <MockWrapper>
          <AIAssistant
            analysisType="lab"
            data={{
              results: [{ parameter: 'Гемоглобин', value: 140 }],
              patient_age: 30,
              patient_gender: 'male'
            }}
            useMCP={true}
          />
        </MockWrapper>
      );

      const refreshButton = screen.getByRole('button', { name: /повторить анализ/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mcpAPI.interpretLabResults).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByText(/в пределах нормы/i)).toBeInTheDocument();
      });
    });
  });
});

