import React, { useState } from 'react';
import { 
  Brain, 
  Loader, 
  Lightbulb, 
  FileText, 
  AlertCircle,
  CheckCircle,
  Zap,
  Search,
  BookOpen,
  Stethoscope
} from 'lucide-react';
import { Card, Button, Badge } from '../../design-system/components';

/**
 * AI Помощник для врачей
 * Основа: passport.md стр. 3325-3888
 */
const AIAssistant = ({ 
  specialty = 'general',
  onSuggestionSelect,
  className = ''
}) => {
  // Проверяем демо-режим в самом начале
  const isDemoMode = window.location.pathname.includes('/medilab-demo') || 
                    window.location.hostname === 'localhost' && 
                    window.location.port === '5173';
  
  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    console.log('AIAssistant: Skipping render in demo mode');
    return null;
  }
  
  const [activeTab, setActiveTab] = useState('complaints');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');

  // Формы для разных типов AI анализа
  const [complaintsForm, setComplaintsForm] = useState({
    complaints: '',
    specialty: specialty,
    language: 'ru'
  });

  const [icd10Form, setIcd10Form] = useState({
    diagnosis: '',
    specialty: specialty,
    language: 'ru'
  });

  const [labForm, setLabForm] = useState({
    lab_results: '',
    patient_age: '',
    patient_gender: 'unknown',
    specialty: specialty
  });

  const tabs = [
    { 
      id: 'complaints', 
      label: 'Анализ жалоб', 
      icon: Stethoscope, 
      color: 'text-blue-600' 
    },
    { 
      id: 'icd10', 
      label: 'МКБ-10', 
      icon: BookOpen, 
      color: 'text-green-600' 
    },
    { 
      id: 'lab', 
      label: 'Анализы', 
      icon: FileText, 
      color: 'text-purple-600' 
    }
  ];

  const handleComplaintsAnalysis = async () => {
    if (!complaintsForm.complaints.trim()) return;

    try {
      setLoading(true);
      setError('');
      setResults(null);

      const response = await fetch('/api/v1/ai/analyze-complaints', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(complaintsForm)
      });

      const result = await response.json();

      if (response.ok && result.success) {
        setResults({
          type: 'complaints',
          data: result.analysis,
          provider: result.provider
        });
      } else {
        throw new Error(result.error || result.detail || 'Ошибка анализа жалоб');
      }

    } catch (err) {
      console.error('Ошибка анализа жалоб:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleIcd10Analysis = async () => {
    if (!icd10Form.diagnosis.trim()) return;

    try {
      setLoading(true);
      setError('');
      setResults(null);

      const response = await fetch('/api/v1/ai/suggest-icd10', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(icd10Form)
      });

      const result = await response.json();

      if (response.ok && result.success) {
        setResults({
          type: 'icd10',
          data: result.suggestions,
          provider: result.provider
        });
      } else {
        throw new Error(result.error || result.detail || 'Ошибка подбора МКБ-10');
      }

    } catch (err) {
      console.error('Ошибка подбора МКБ-10:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLabAnalysis = async () => {
    if (!labForm.lab_results.trim()) return;

    try {
      setLoading(true);
      setError('');
      setResults(null);

      const response = await fetch('/api/v1/ai/interpret-lab-results', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(labForm)
      });

      const result = await response.json();

      if (response.ok && result.success) {
        setResults({
          type: 'lab',
          data: result.analysis,
          provider: result.provider
        });
      } else {
        throw new Error(result.error || result.detail || 'Ошибка анализа результатов');
      }

    } catch (err) {
      console.error('Ошибка анализа результатов:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const renderComplaintsTab = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Жалобы пациента:
        </label>
        <textarea
          value={complaintsForm.complaints}
          onChange={(e) => setComplaintsForm({ ...complaintsForm, complaints: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          rows={4}
          placeholder="Опишите жалобы пациента..."
        />
      </div>

      <Button
        onClick={handleComplaintsAnalysis}
        disabled={loading || !complaintsForm.complaints.trim()}
        className="w-full"
      >
        {loading ? (
          <Loader size={16} className="animate-spin mr-2" />
        ) : (
          <Brain size={16} className="mr-2" />
        )}
        Анализировать жалобы
      </Button>
    </div>
  );

  const renderIcd10Tab = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Диагноз:
        </label>
        <input
          type="text"
          value={icd10Form.diagnosis}
          onChange={(e) => setIcd10Form({ ...icd10Form, diagnosis: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          placeholder="Введите диагноз..."
        />
      </div>

      <Button
        onClick={handleIcd10Analysis}
        disabled={loading || !icd10Form.diagnosis.trim()}
        className="w-full"
        variant="success"
      >
        {loading ? (
          <Loader size={16} className="animate-spin mr-2" />
        ) : (
          <Search size={16} className="mr-2" />
        )}
        Найти коды МКБ-10
      </Button>
    </div>
  );

  const renderLabTab = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Результаты анализов:
        </label>
        <textarea
          value={labForm.lab_results}
          onChange={(e) => setLabForm({ ...labForm, lab_results: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          rows={4}
          placeholder="Введите результаты анализов..."
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Возраст:
          </label>
          <input
            type="number"
            value={labForm.patient_age}
            onChange={(e) => setLabForm({ ...labForm, patient_age: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            placeholder="35"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Пол:
          </label>
          <select
            value={labForm.patient_gender}
            onChange={(e) => setLabForm({ ...labForm, patient_gender: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          >
            <option value="unknown">Не указан</option>
            <option value="male">Мужской</option>
            <option value="female">Женский</option>
          </select>
        </div>
      </div>

      <Button
        onClick={handleLabAnalysis}
        disabled={loading || !labForm.lab_results.trim()}
        className="w-full"
        variant="outline"
      >
        {loading ? (
          <Loader size={16} className="animate-spin mr-2" />
        ) : (
          <FileText size={16} className="mr-2" />
        )}
        Интерпретировать результаты
      </Button>
    </div>
  );

  const renderResults = () => {
    if (!results) return null;

    return (
      <Card className="mt-6 p-4 bg-blue-50 border-blue-200 dark:bg-blue-900/20">
        <div className="flex items-center mb-3">
          <Brain size={20} className="mr-2 text-blue-600" />
          <h4 className="font-medium text-blue-800 dark:text-blue-400">
            AI Анализ
          </h4>
          <Badge variant="outline" size="sm" className="ml-2">
            {results.provider}
          </Badge>
        </div>

        {results.type === 'complaints' && (
          <div className="space-y-3">
            {results.data.analysis_text && (
              <div>
                <h5 className="font-medium text-sm text-gray-700 dark:text-gray-300">Анализ:</h5>
                <p className="text-sm text-gray-600 dark:text-gray-400">{results.data.analysis_text}</p>
              </div>
            )}
            
            {results.data.possible_diagnoses && results.data.possible_diagnoses.length > 0 && (
              <div>
                <h5 className="font-medium text-sm text-gray-700 dark:text-gray-300">Возможные диагнозы:</h5>
                <ul className="text-sm text-gray-600 dark:text-gray-400 list-disc list-inside">
                  {results.data.possible_diagnoses.map((diagnosis, index) => (
                    <li key={index}>{diagnosis}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {results.type === 'icd10' && (
          <div className="space-y-2">
            {results.data.map((code, index) => (
              <div 
                key={index}
                className="flex items-center justify-between p-2 bg-white dark:bg-gray-800 rounded border cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700"
                onClick={() => {
                  if (onSuggestionSelect) {
                    onSuggestionSelect('icd10', code.code);
                  }
                }}
              >
                <div>
                  <div className="font-mono text-sm font-medium">{code.code}</div>
                  <div className="text-xs text-gray-500">{code.description}</div>
                </div>
                <Button size="sm" variant="outline">
                  Выбрать
                </Button>
              </div>
            ))}
          </div>
        )}

        {results.type === 'lab' && (
          <div className="space-y-3">
            {results.data.summary && (
              <div>
                <h5 className="font-medium text-sm text-gray-700 dark:text-gray-300">Заключение:</h5>
                <p className="text-sm text-gray-600 dark:text-gray-400">{results.data.summary}</p>
              </div>
            )}
          </div>
        )}
      </Card>
    );
  };

  return (
    <Card className={`p-4 ${className}`}>
      <div className="flex items-center mb-4">
        <Brain size={24} className="mr-3 text-blue-600" />
        <h3 className="text-lg font-medium">AI Помощник</h3>
        <Badge variant="info" size="sm" className="ml-2">
          {specialty === 'cardio' ? 'Кардиология' : 
           specialty === 'derma' ? 'Дерматология' :
           specialty === 'dentist' ? 'Стоматология' : 'Общий'}
        </Badge>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          <AlertCircle size={16} className="inline mr-2" />
          {error}
        </div>
      )}

      {/* Вкладки */}
      <div className="flex space-x-1 mb-4">
        {tabs.map(tab => {
          const isActive = activeTab === tab.id;
          const TabIcon = tab.icon;
          
          return (
            <button
              key={tab.id}
              className={`flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                isActive
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
              onClick={() => setActiveTab(tab.id)}
            >
              <TabIcon size={16} className="mr-1" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Контент вкладок */}
      <div>
        {activeTab === 'complaints' && renderComplaintsTab()}
        {activeTab === 'icd10' && renderIcd10Tab()}
        {activeTab === 'lab' && renderLabTab()}
      </div>

      {/* Результаты */}
      {renderResults()}

      {/* Подсказки */}
      <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
        <div className="flex items-center text-sm text-gray-600 dark:text-gray-400">
          <Lightbulb size={14} className="mr-2" />
          <span>
            {activeTab === 'complaints' && 'Опишите жалобы пациента для получения рекомендаций по обследованию'}
            {activeTab === 'icd10' && 'Введите диагноз для автоподбора кодов МКБ-10'}
            {activeTab === 'lab' && 'Вставьте результаты анализов для интерпретации'}
          </span>
        </div>
      </div>
    </Card>
  );
};

export default AIAssistant;
