/**
 * Lab Results Manager Component
 * Управление результатами лабораторных исследований
 * Согласно MASTER_TODO_LIST строка 287
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Input,
  Alert,
  CircularProgress,
  Badge,
  Select,
  Option,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Progress
} from '../ui/macos';
import {
  TestTube,
  Plus,
  Edit,
  Trash2,
  Eye,
  Download,
  Upload,
  Printer,
  Send,
  AlertTriangle,
  CheckCircle,
  Calendar,
  TrendingUp,
  TrendingDown,
  Minus,
  Microscope,
  Hospital,
  Brain,
} from 'lucide-react';
import { api } from '../../api/client';
import { AIButton, AIAssistant } from '../ai';

// Категории анализов
const LAB_CATEGORIES = {
  blood: { name: 'Анализы крови', icon: <TestTube style={{ color: 'var(--mac-accent-red)' }} /> },
  urine: { name: 'Анализы мочи', icon: <TestTube style={{ color: 'var(--mac-accent-orange)' }} /> },
  biochemistry: { name: 'Биохимия', icon: <Microscope style={{ color: 'var(--mac-accent-blue)' }} /> },
  hormones: { name: 'Гормоны', icon: <Hospital style={{ color: 'var(--mac-accent-purple)' }} /> },
  other: { name: 'Другие', icon: <TestTube /> },
};

// Статусы результатов
const RESULT_STATUS = {
  pending: { label: 'Ожидается', color: 'warning' },
  in_progress: { label: 'В работе', color: 'info' },
  completed: { label: 'Готов', color: 'success' },
  abnormal: { label: 'Отклонения', color: 'error' },
};

const LabResultsManager = ({ patientId, visitId, onUpdate }) => {
  const [activeTab, setActiveTab] = useState('all');
  const [results, setResults] = useState([]);
  const [selectedResult, setSelectedResult] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [uploadDialog, setUploadDialog] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showAIAnalysis, setShowAIAnalysis] = useState(false);
  const [aiAnalysisResults, setAiAnalysisResults] = useState(null);
  
  // Форма результата
  const [resultForm, setResultForm] = useState({
    test_name: '',
    category: 'blood',
    value: '',
    unit: '',
    reference_min: '',
    reference_max: '',
    status: 'pending',
    notes: '',
    performed_date: new Date().toISOString().split('T')[0],
  });

  // Загрузка результатов
  useEffect(() => {
    if (visitId) {
      loadResults();
    }
  }, [visitId]);

  const loadResults = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/visits/${visitId}/lab-results`);
      setResults(response.data || []);
    } catch (error) {
      console.error('Ошибка загрузки результатов:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  // Фильтрация результатов
  const filteredResults = activeTab === 'all' 
    ? results 
    : results.filter(r => r.category === activeTab);

  // Подсчет по категориям
  const getCategoryCount = (category) => {
    return results.filter(r => r.category === category).length;
  };

  // Определение статуса по значению
  const determineStatus = (value, min, max) => {
    const numValue = parseFloat(value);
    const numMin = parseFloat(min);
    const numMax = parseFloat(max);
    
    if (isNaN(numValue) || isNaN(numMin) || isNaN(numMax)) {
      return 'completed';
    }
    
    if (numValue < numMin || numValue > numMax) {
      return 'abnormal';
    }
    
    return 'completed';
  };

  // Сохранение результата
  const handleSaveResult = async () => {
    try {
      const status = determineStatus(
        resultForm.value,
        resultForm.reference_min,
        resultForm.reference_max
      );
      
      const dataToSave = {
        ...resultForm,
        status,
        visit_id: visitId,
        patient_id: patientId,
      };
      
      if (selectedResult) {
        await api.put(`/lab-results/${selectedResult.id}`, dataToSave);
      } else {
        await api.post('/lab-results', dataToSave);
      }
      
      loadResults();
      setDialogOpen(false);
      resetForm();
      onUpdate && onUpdate();
      
    } catch (error) {
      console.error('Ошибка сохранения результата:', error);
    }
  };

  // Удаление результата
  const handleDeleteResult = async (resultId) => {
    if (!window.confirm('Удалить результат?')) return;
    
    try {
      await api.delete(`/lab-results/${resultId}`);
      loadResults();
      onUpdate && onUpdate();
    } catch (error) {
      console.error('Ошибка удаления результата:', error);
    }
  };

  // Загрузка файла с результатами
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('visit_id', visitId);
    formData.append('patient_id', patientId);
    
    try {
      setLoading(true);
      const response = await api.post('/lab-results/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      
      if (response.data.results) {
        setResults(prev => [...prev, ...response.data.results]);
      }
      
      setUploadDialog(false);
      onUpdate && onUpdate();
      
    } catch (error) {
      console.error('Ошибка загрузки файла:', error);
    } finally {
      setLoading(false);
    }
  };

  // Экспорт в PDF
  const exportToPDF = async () => {
    try {
      const response = await api.get(`/visits/${visitId}/lab-results/pdf`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `lab_results_${visitId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
    } catch (error) {
      console.error('Ошибка экспорта PDF:', error);
    }
  };

  // Отправка пациенту
  const sendToPatient = async () => {
    try {
      await api.post(`/patients/${patientId}/send-lab-results`, {
        visit_id: visitId,
        method: 'telegram',
      });
      
      alert('Результаты отправлены пациенту');
    } catch (error) {
      console.error('Ошибка отправки результатов:', error);
    }
  };

  // Сброс формы
  const resetForm = () => {
    setResultForm({
      test_name: '',
      category: 'blood',
      value: '',
      unit: '',
      reference_min: '',
      reference_max: '',
      status: 'pending',
      notes: '',
      performed_date: new Date().toISOString().split('T')[0],
    });
    setSelectedResult(null);
  };

  // Отображение значения с индикатором
  const renderValue = (result) => {
    const isAbnormal = result.status === 'abnormal';
    const value = parseFloat(result.value);
    const min = parseFloat(result.reference_min);
    const max = parseFloat(result.reference_max);
    
    let trend = null;
    if (!isNaN(value) && !isNaN(min) && !isNaN(max)) {
      if (value < min) trend = 'low';
      else if (value > max) trend = 'high';
    }
    
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="body2" color={isAbnormal ? 'error' : 'text.primary'}>
          {result.value} {result.unit}
        </Typography>
        {trend === 'low' && <TrendingDown color="error" fontSize="small" />}
        {trend === 'high' && <TrendingUp color="error" fontSize="small" />}
      </Box>
    );
  };

  return (
    <Box>
      <Card>
        <CardContent>
          <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <Typography variant="h6">
              <TestTube style={{ marginRight: 8, verticalAlign: 'middle' }} />
              Лабораторные исследования
            </Typography>
            
            <Box style={{ display: 'flex', gap: 8 }}>
              <Button size="small" onClick={() => setDialogOpen(true)}>
                <Plus style={{ width: 16, height: 16, marginRight: 8 }} />
                Добавить результат
              </Button>
              <Button size="small" onClick={() => setUploadDialog(true)}>
                <Upload style={{ width: 16, height: 16, marginRight: 8 }} />
                Загрузить файл
              </Button>
              <Button size="small" onClick={exportToPDF}>
                <Download style={{ width: 16, height: 16, marginRight: 8 }} />
                Экспорт PDF
              </Button>
              <Button size="small" onClick={sendToPatient}>
                <Send style={{ width: 16, height: 16, marginRight: 8 }} />
                Отправить
              </Button>
              <AIButton
                text="AI Анализ"
                size="small"
                onClick={() => {
                  if (results.length > 0) {
                    setShowAIAnalysis(true);
                  }
                }}
                disabled={results.length === 0}
                tooltip="AI интерпретация результатов"
              />
            </Box>
          </Box>

          {/* Табы категорий */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--mac-border)', marginBottom: 16 }}>
            <button
              style={{
                padding: '12px 24px',
                border: 'none',
                background: activeTab === 'all' ? 'var(--mac-accent-blue)' : 'transparent',
                color: activeTab === 'all' ? 'white' : 'var(--mac-text-primary)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}
              onClick={() => setActiveTab('all')}
            >
              Все
              <Badge variant="primary">{results.length}</Badge>
            </button>
            {Object.entries(LAB_CATEGORIES).map(([key, category]) => (
              <button
                key={key}
                style={{
                  padding: '12px 24px',
                  border: 'none',
                  background: activeTab === key ? 'var(--mac-accent-blue)' : 'transparent',
                  color: activeTab === key ? 'white' : 'var(--mac-text-primary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}
                onClick={() => setActiveTab(key)}
              >
                {category.icon}
                {category.name}
                <Badge variant="primary">{getCategoryCount(key)}</Badge>
              </button>
            ))}
          </div>

          {/* Таблица результатов */}
          {loading ? (
            <Progress />
          ) : filteredResults.length > 0 ? (
            <div style={{ overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--mac-border)' }}>
                    <th style={{ padding: 12, textAlign: 'left' }}>Исследование</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Результат</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Норма</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Статус</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Дата</th>
                    <th style={{ padding: 12, textAlign: 'right' }}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((result) => (
                    <tr key={result.id} style={{ borderBottom: '1px solid var(--mac-border)' }}>
                      <td style={{ padding: 12 }}>
                        <Typography variant="body2" style={{ fontWeight: 500 }}>
                          {result.test_name}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          {LAB_CATEGORIES[result.category]?.name}
                        </Typography>
                      </td>
                      
                      <td style={{ padding: 12 }}>{renderValue(result)}</td>
                      
                      <td style={{ padding: 12 }}>
                        <Typography variant="caption">
                          {result.reference_min} - {result.reference_max} {result.unit}
                        </Typography>
                      </td>
                      
                      <td style={{ padding: 12 }}>
                        <Badge
                          variant={RESULT_STATUS[result.status]?.color}
                        >
                          {RESULT_STATUS[result.status]?.label}
                        </Badge>
                      </td>
                      
                      <td style={{ padding: 12 }}>
                        <Typography variant="caption">
                          {new Date(result.performed_date).toLocaleDateString()}
                        </Typography>
                      </td>
                      
                      <td style={{ padding: 12, textAlign: 'right' }}>
                        <Button
                          size="small"
                          onClick={() => {
                            setSelectedResult(result);
                            setResultForm(result);
                            setDialogOpen(true);
                          }}
                        >
                          <Edit style={{ width: 16, height: 16 }} />
                        </Button>
                        <Button
                          size="small"
                          variant="danger"
                          onClick={() => handleDeleteResult(result.id)}
                        >
                          <Delete style={{ width: 16, height: 16 }} />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Alert severity="info">
              Нет результатов анализов. Добавьте новый результат или загрузите файл.
            </Alert>
          )}

          {/* Сводка по отклонениям */}
          {results.filter(r => r.status === 'abnormal').length > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Обнаружены отклонения:
              </Typography>
              {results
                .filter(r => r.status === 'abnormal')
                .map((result, index) => (
                  <Typography key={index} variant="body2">
                    • {result.test_name}: {result.value} {result.unit} 
                    (норма: {result.reference_min}-{result.reference_max})
                  </Typography>
                ))}
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Диалог добавления/редактирования */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {selectedResult ? 'Редактировать результат' : 'Добавить результат'}
        </DialogTitle>
        
        <DialogContent>
          <Box style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '8px' }}>
            <Box style={{ display: 'flex', gap: '16px' }}>
              <Box style={{ flex: 2 }}>
                <Input
                  label="Название исследования"
                  value={resultForm.test_name}
                  onChange={(e) => setResultForm({ ...resultForm, test_name: e.target.value })}
                />
              </Box>
              
              <Box style={{ flex: 1 }}>
                <Select
                  label="Категория"
                  value={resultForm.category}
                  onChange={(e) => setResultForm({ ...resultForm, category: e.target.value })}
                >
                  {Object.entries(LAB_CATEGORIES).map(([key, category]) => (
                    <Option key={key} value={key}>
                      {category.name}
                    </Option>
                  ))}
                </Select>
              </Box>
            </Box>
            
            <Box style={{ display: 'flex', gap: '16px' }}>
              <Box style={{ flex: 2 }}>
                <Input
                  label="Результат"
                  value={resultForm.value}
                  onChange={(e) => setResultForm({ ...resultForm, value: e.target.value })}
                />
              </Box>
              
              <Box style={{ flex: 1 }}>
                <Input
                  label="Ед."
                  value={resultForm.unit}
                  onChange={(e) => setResultForm({ ...resultForm, unit: e.target.value })}
                />
              </Box>
              
              <Box style={{ flex: 1 }}>
                <Input
                  label="Мин. норма"
                  value={resultForm.reference_min}
                  onChange={(e) => setResultForm({ ...resultForm, reference_min: e.target.value })}
                />
              </Box>
              
              <Box style={{ flex: 1 }}>
                <Input
                  label="Макс. норма"
                  value={resultForm.reference_max}
                  onChange={(e) => setResultForm({ ...resultForm, reference_max: e.target.value })}
                />
              </Box>
            </Box>
            
            <Box style={{ display: 'flex', gap: '16px' }}>
              <Box style={{ flex: 1 }}>
                <Input
                  type="date"
                  label="Дата выполнения"
                  value={resultForm.performed_date}
                  onChange={(e) => setResultForm({ ...resultForm, performed_date: e.target.value })}
                />
              </Box>
            </Box>
            
            <Box>
              <Input
                multiline
                rows={2}
                label="Примечания"
                value={resultForm.notes}
                onChange={(e) => setResultForm({ ...resultForm, notes: e.target.value })}
              />
            </Box>
          </Box>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => {
            setDialogOpen(false);
            resetForm();
          }}>
            Отмена
          </Button>
          <Button variant="contained" onClick={handleSaveResult} disabled={!resultForm.test_name}>
            {selectedResult ? 'Сохранить' : 'Добавить'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог загрузки файла */}
      <Dialog open={uploadDialog} onClose={() => setUploadDialog(false)}>
        <DialogTitle>Загрузить файл с результатами</DialogTitle>
        
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            Поддерживаются форматы: PDF, Excel, CSV
          </Alert>
          
          <input
            type="file"
            accept=".pdf,.xlsx,.xls,.csv"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
            id="lab-file-upload"
          />
          
          <label htmlFor="lab-file-upload">
            <Button
              variant="contained"
              component="span"
              fullWidth
              startIcon={<Upload />}
            >
              Выбрать файл
            </Button>
          </label>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setUploadDialog(false)}>
            Закрыть
          </Button>
        </DialogActions>
      </Dialog>

      {/* AI Analysis Dialog */}
      {showAIAnalysis && (
        <Dialog 
          open={showAIAnalysis} 
          onClose={() => setShowAIAnalysis(false)} 
          maxWidth="md" 
          fullWidth
        >
          <DialogTitle>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="h6">
                <Psychology sx={{ mr: 1, verticalAlign: 'middle' }} />
                AI Интерпретация результатов
              </Typography>
              <IconButton onClick={() => setShowAIAnalysis(false)}>
                <Remove />
              </IconButton>
            </Box>
          </DialogTitle>
          
          <DialogContent>
            <AIAssistant
              analysisType="lab"
              data={{
                results: results.map(r => ({
                  name: r.test_name,
                  value: r.value,
                  unit: r.unit,
                  reference: `${r.reference_min}-${r.reference_max}`
                })),
                patient_age: patientId ? 35 : null, // Здесь нужно получить реальный возраст
                patient_gender: null
              }}
              onResult={(result) => {
                setAiAnalysisResults(result);
              }}
            />
          </DialogContent>
          
          <DialogActions>
            <Button onClick={() => setShowAIAnalysis(false)}>
              Закрыть
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  );
};

export default LabResultsManager;

