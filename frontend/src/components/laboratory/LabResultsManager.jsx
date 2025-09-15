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
  TextField,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  InputAdornment,
  Tabs,
  Tab,
  Badge,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Science,
  Add,
  Edit,
  Delete,
  Visibility,
  Download,
  Upload,
  Print,
  Send,
  Warning,
  CheckCircle,
  Schedule,
  TrendingUp,
  TrendingDown,
  Remove,
  Biotech,
  LocalHospital,
} from '@mui/icons-material';
import { api } from '../../api/client';

// Категории анализов
const LAB_CATEGORIES = {
  blood: { name: 'Анализы крови', icon: <Science color="error" /> },
  urine: { name: 'Анализы мочи', icon: <Science color="warning" /> },
  biochemistry: { name: 'Биохимия', icon: <Biotech color="primary" /> },
  hormones: { name: 'Гормоны', icon: <LocalHospital color="secondary" /> },
  other: { name: 'Другие', icon: <Science /> },
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
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h6">
              <Science sx={{ mr: 1, verticalAlign: 'middle' }} />
              Лабораторные исследования
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button size="small" startIcon={<Add />} onClick={() => setDialogOpen(true)}>
                Добавить результат
              </Button>
              <Button size="small" startIcon={<Upload />} onClick={() => setUploadDialog(true)}>
                Загрузить файл
              </Button>
              <Button size="small" startIcon={<Download />} onClick={exportToPDF}>
                Экспорт PDF
              </Button>
              <Button size="small" startIcon={<Send />} onClick={sendToPatient}>
                Отправить
              </Button>
            </Box>
          </Box>

          {/* Табы категорий */}
          <Tabs value={activeTab} onChange={(e, value) => setActiveTab(value)} sx={{ mb: 2 }}>
            <Tab 
              label="Все" 
              value="all"
              icon={<Badge badgeContent={results.length} color="primary" />}
            />
            {Object.entries(LAB_CATEGORIES).map(([key, category]) => (
              <Tab
                key={key}
                label={category.name}
                value={key}
                icon={
                  <Badge badgeContent={getCategoryCount(key)} color="primary">
                    {category.icon}
                  </Badge>
                }
              />
            ))}
          </Tabs>

          {/* Таблица результатов */}
          {loading ? (
            <LinearProgress />
          ) : filteredResults.length > 0 ? (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Исследование</TableCell>
                    <TableCell>Результат</TableCell>
                    <TableCell>Норма</TableCell>
                    <TableCell>Статус</TableCell>
                    <TableCell>Дата</TableCell>
                    <TableCell align="right">Действия</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredResults.map((result) => (
                    <TableRow key={result.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {result.test_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {LAB_CATEGORIES[result.category]?.name}
                        </Typography>
                      </TableCell>
                      
                      <TableCell>{renderValue(result)}</TableCell>
                      
                      <TableCell>
                        <Typography variant="caption">
                          {result.reference_min} - {result.reference_max} {result.unit}
                        </Typography>
                      </TableCell>
                      
                      <TableCell>
                        <Chip
                          size="small"
                          label={RESULT_STATUS[result.status]?.label}
                          color={RESULT_STATUS[result.status]?.color}
                        />
                      </TableCell>
                      
                      <TableCell>
                        <Typography variant="caption">
                          {new Date(result.performed_date).toLocaleDateString()}
                        </Typography>
                      </TableCell>
                      
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          onClick={() => {
                            setSelectedResult(result);
                            setResultForm(result);
                            setDialogOpen(true);
                          }}
                        >
                          <Edit />
                        </IconButton>
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteResult(result.id)}
                        >
                          <Delete />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
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
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={8}>
              <TextField
                fullWidth
                label="Название исследования"
                value={resultForm.test_name}
                onChange={(e) => setResultForm({ ...resultForm, test_name: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12} md={4}>
              <FormControl fullWidth>
                <InputLabel>Категория</InputLabel>
                <Select
                  value={resultForm.category}
                  onChange={(e) => setResultForm({ ...resultForm, category: e.target.value })}
                  label="Категория"
                >
                  {Object.entries(LAB_CATEGORIES).map(([key, category]) => (
                    <MenuItem key={key} value={key}>
                      {category.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label="Результат"
                value={resultForm.value}
                onChange={(e) => setResultForm({ ...resultForm, value: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                label="Ед."
                value={resultForm.unit}
                onChange={(e) => setResultForm({ ...resultForm, unit: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Мин. норма"
                value={resultForm.reference_min}
                onChange={(e) => setResultForm({ ...resultForm, reference_min: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Макс. норма"
                value={resultForm.reference_max}
                onChange={(e) => setResultForm({ ...resultForm, reference_max: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="date"
                label="Дата выполнения"
                value={resultForm.performed_date}
                onChange={(e) => setResultForm({ ...resultForm, performed_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Примечания"
                value={resultForm.notes}
                onChange={(e) => setResultForm({ ...resultForm, notes: e.target.value })}
              />
            </Grid>
          </Grid>
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
    </Box>
  );
};

export default LabResultsManager;
