/**
 * Echo Form Component
 * Форма для ввода результатов ЭхоКГ
 * Согласно MASTER_TODO_LIST строка 248
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Grid,
  Button,
  Alert,
  Divider,
  Paper,
  Chip,
  IconButton,
  Collapse,
  FormControlLabel,
  Checkbox,
  InputAdornment,
} from '@mui/material';
import {
  Favorite,
  Analytics,
  Save,
  ExpandMore,
  ExpandLess,
  CloudUpload,
  AutoFixHigh,
  Warning,
  CheckCircle,
} from '@mui/icons-material';
import { api } from '../../api/client';

const EchoForm = ({ visitId, patientId, onDataUpdate }) => {
  const [expanded, setExpanded] = useState(true);
  const [echoData, setEchoData] = useState({
    // Размеры камер
    leftVentricle: {
      edd: '', // End-diastolic dimension
      esd: '', // End-systolic dimension
      edv: '', // End-diastolic volume
      esv: '', // End-systolic volume
      ef: '', // Ejection fraction
      fs: '', // Fractional shortening
    },
    leftAtrium: {
      diameter: '',
      volume: '',
    },
    rightVentricle: {
      diameter: '',
    },
    rightAtrium: {
      diameter: '',
    },
    
    // Толщина стенок
    walls: {
      ivs: '', // Interventricular septum
      pw: '', // Posterior wall
    },
    
    // Клапаны
    valves: {
      mitral: {
        regurgitation: '',
        stenosis: false,
        gradient: '',
      },
      aortic: {
        regurgitation: '',
        stenosis: false,
        gradient: '',
      },
      tricuspid: {
        regurgitation: '',
        gradient: '',
      },
      pulmonary: {
        regurgitation: '',
      },
    },
    
    // Дополнительно
    diastolicFunction: '',
    pericardialEffusion: false,
    conclusion: '',
    recommendations: '',
  });
  
  const [aiAnalyzing, setAiAnalyzing] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Загрузка существующих данных
  useEffect(() => {
    loadEchoData();
  }, [visitId]);

  const loadEchoData = async () => {
    // В демо-режиме (visitId вроде 'demo-visit-*') не дергаем бэкенд
    if (!visitId || (typeof visitId === 'string' && visitId.startsWith('demo-visit'))) {
      return;
    }
    try {
      const response = await api.get(`/visits/${visitId}/echo/params`);
      if (response.data) {
        setEchoData(response.data);
      }
    } catch (error) {
      // Если бэкенд не реализован (404) — тихо используем значения по умолчанию
      if (error?.response?.status === 404) {
        console.info('Echo params endpoint not found (404). Using defaults.');
        return;
      }
      console.error('Ошибка загрузки данных ЭхоКГ:', error);
    }
  };

  // Обновление данных
  const handleChange = (section, field, value) => {
    setEchoData(prev => ({
      ...prev,
      [section]: typeof prev[section] === 'object'
        ? { ...prev[section], [field]: value }
        : value,
    }));
    setSaved(false);
  };

  // Обновление вложенных данных
  const handleNestedChange = (section, subsection, field, value) => {
    setEchoData(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [subsection]: {
          ...prev[section][subsection],
          [field]: value,
        },
      },
    }));
    setSaved(false);
  };

  // Расчет фракции выброса
  const calculateEF = () => {
    const { edv, esv } = echoData.leftVentricle;
    if (edv && esv) {
      const ef = Math.round(((edv - esv) / edv) * 100);
      handleChange('leftVentricle', 'ef', ef.toString());
    }
  };

  // AI интерпретация
  const analyzeWithAI = async () => {
    setAiAnalyzing(true);
    setAiResult(null);
    
    try {
      const response = await api.post('/ai/echo-interpret', {
        visit_id: visitId,
        patient_id: patientId,
        parameters: echoData,
      });
      
      setAiResult(response.data);
      
      // Автозаполнение заключения если AI предложил
      if (response.data.conclusion) {
        setEchoData(prev => ({
          ...prev,
          conclusion: response.data.conclusion,
          recommendations: response.data.recommendations || prev.recommendations,
        }));
      }
      
    } catch (error) {
      console.error('Ошибка AI анализа:', error);
      setAiResult({ error: 'Не удалось проанализировать данные' });
    } finally {
      setAiAnalyzing(false);
    }
  };

  // Сохранение данных
  const saveEchoData = async () => {
    setSaving(true);
    
    try {
      await api.post(`/visits/${visitId}/echo/params`, echoData);
      setSaved(true);
      onDataUpdate && onDataUpdate();
      
      setTimeout(() => setSaved(false), 3000);
      
    } catch (error) {
      console.error('Ошибка сохранения:', error);
    } finally {
      setSaving(false);
    }
  };

  // Определение нормальности значений
  const isNormal = (value, min, max) => {
    const num = parseFloat(value);
    if (!num) return null;
    return num >= min && num <= max;
  };

  // Получение статуса фракции выброса
  const getEFStatus = (ef) => {
    const value = parseFloat(ef);
    if (!value) return null;
    
    if (value >= 55) return { label: 'Норма', color: 'success' };
    if (value >= 45) return { label: 'Умеренное снижение', color: 'warning' };
    if (value >= 35) return { label: 'Снижение средней степени', color: 'warning' };
    return { label: 'Выраженное снижение', color: 'error' };
  };

  const efStatus = getEFStatus(echoData.leftVentricle.ef);

  return (
    <Box>
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">
              <Favorite sx={{ mr: 1, verticalAlign: 'middle', color: 'error.main' }} />
              Эхокардиография (ЭхоКГ)
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 1 }}>
              <IconButton onClick={() => setExpanded(!expanded)}>
                {expanded ? <ExpandLess /> : <ExpandMore />}
              </IconButton>
            </Box>
          </Box>
          
          <Collapse in={expanded}>
            {/* Размеры левого желудочка */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Левый желудочек
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="КДР"
                    value={echoData.leftVentricle.edd}
                    onChange={(e) => handleChange('leftVentricle', 'edd', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мм</InputAdornment>,
                    }}
                    helperText="Норма: 35-55 мм"
                  />
                </Grid>
                
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="КСР"
                    value={echoData.leftVentricle.esd}
                    onChange={(e) => handleChange('leftVentricle', 'esd', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мм</InputAdornment>,
                    }}
                    helperText="Норма: 25-40 мм"
                  />
                </Grid>
                
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="КДО"
                    value={echoData.leftVentricle.edv}
                    onChange={(e) => handleChange('leftVentricle', 'edv', e.target.value)}
                    onBlur={calculateEF}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мл</InputAdornment>,
                    }}
                    helperText="Норма: 55-150 мл"
                  />
                </Grid>
                
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="КСО"
                    value={echoData.leftVentricle.esv}
                    onChange={(e) => handleChange('leftVentricle', 'esv', e.target.value)}
                    onBlur={calculateEF}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мл</InputAdornment>,
                    }}
                    helperText="Норма: 20-60 мл"
                  />
                </Grid>
                
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Фракция выброса"
                    value={echoData.leftVentricle.ef}
                    onChange={(e) => handleChange('leftVentricle', 'ef', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">%</InputAdornment>,
                    }}
                    helperText="Норма: >55%"
                    error={efStatus?.color === 'error'}
                    color={efStatus?.color === 'success' ? 'success' : undefined}
                  />
                  {efStatus && (
                    <Chip
                      size="small"
                      label={efStatus.label}
                      color={efStatus.color}
                      icon={efStatus.color === 'success' ? <CheckCircle /> : <Warning />}
                      sx={{ mt: 1 }}
                    />
                  )}
                </Grid>
                
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Фракция укорочения"
                    value={echoData.leftVentricle.fs}
                    onChange={(e) => handleChange('leftVentricle', 'fs', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">%</InputAdornment>,
                    }}
                    helperText="Норма: 25-45%"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Толщина стенок */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Толщина стенок
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <TextField
                    fullWidth
                    size="small"
                    label="МЖП"
                    value={echoData.walls.ivs}
                    onChange={(e) => handleChange('walls', 'ivs', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мм</InputAdornment>,
                    }}
                    helperText="Норма: 6-11 мм"
                  />
                </Grid>
                
                <Grid item xs={6}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Задняя стенка"
                    value={echoData.walls.pw}
                    onChange={(e) => handleChange('walls', 'pw', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мм</InputAdornment>,
                    }}
                    helperText="Норма: 6-11 мм"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Предсердия */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Предсердия
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Левое предсердие"
                    value={echoData.leftAtrium.diameter}
                    onChange={(e) => handleChange('leftAtrium', 'diameter', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мм</InputAdornment>,
                    }}
                    helperText="Норма: 20-40 мм"
                  />
                </Grid>
                
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Объем ЛП"
                    value={echoData.leftAtrium.volume}
                    onChange={(e) => handleChange('leftAtrium', 'volume', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мл</InputAdornment>,
                    }}
                  />
                </Grid>
                
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Правое предсердие"
                    value={echoData.rightAtrium.diameter}
                    onChange={(e) => handleChange('rightAtrium', 'diameter', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мм</InputAdornment>,
                    }}
                  />
                </Grid>
                
                <Grid item xs={6} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Правый желудочек"
                    value={echoData.rightVentricle.diameter}
                    onChange={(e) => handleChange('rightVentricle', 'diameter', e.target.value)}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">мм</InputAdornment>,
                    }}
                    helperText="Норма: <30 мм"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Клапаны */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Клапанный аппарат
              </Typography>
              
              <Grid container spacing={2}>
                {/* Митральный клапан */}
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" gutterBottom>
                    Митральный клапан
                  </Typography>
                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Регургитация"
                        value={echoData.valves.mitral.regurgitation}
                        onChange={(e) => handleNestedChange('valves', 'mitral', 'regurgitation', e.target.value)}
                        placeholder="0-4 ст."
                      />
                    </Grid>
                    <Grid item xs={6}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Градиент"
                        value={echoData.valves.mitral.gradient}
                        onChange={(e) => handleNestedChange('valves', 'mitral', 'gradient', e.target.value)}
                        InputProps={{
                          endAdornment: <InputAdornment position="end">мм рт.ст.</InputAdornment>,
                        }}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={echoData.valves.mitral.stenosis}
                            onChange={(e) => handleNestedChange('valves', 'mitral', 'stenosis', e.target.checked)}
                          />
                        }
                        label="Стеноз"
                      />
                    </Grid>
                  </Grid>
                </Grid>
                
                {/* Аортальный клапан */}
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" gutterBottom>
                    Аортальный клапан
                  </Typography>
                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Регургитация"
                        value={echoData.valves.aortic.regurgitation}
                        onChange={(e) => handleNestedChange('valves', 'aortic', 'regurgitation', e.target.value)}
                        placeholder="0-4 ст."
                      />
                    </Grid>
                    <Grid item xs={6}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Градиент"
                        value={echoData.valves.aortic.gradient}
                        onChange={(e) => handleNestedChange('valves', 'aortic', 'gradient', e.target.value)}
                        InputProps={{
                          endAdornment: <InputAdornment position="end">мм рт.ст.</InputAdornment>,
                        }}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={echoData.valves.aortic.stenosis}
                            onChange={(e) => handleNestedChange('valves', 'aortic', 'stenosis', e.target.checked)}
                          />
                        }
                        label="Стеноз"
                      />
                    </Grid>
                  </Grid>
                </Grid>
                
                {/* Трикуспидальный клапан */}
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" gutterBottom>
                    Трикуспидальный клапан
                  </Typography>
                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Регургитация"
                        value={echoData.valves.tricuspid.regurgitation}
                        onChange={(e) => handleNestedChange('valves', 'tricuspid', 'regurgitation', e.target.value)}
                        placeholder="0-4 ст."
                      />
                    </Grid>
                    <Grid item xs={6}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Градиент"
                        value={echoData.valves.tricuspid.gradient}
                        onChange={(e) => handleNestedChange('valves', 'tricuspid', 'gradient', e.target.value)}
                        InputProps={{
                          endAdornment: <InputAdornment position="end">мм рт.ст.</InputAdornment>,
                        }}
                      />
                    </Grid>
                  </Grid>
                </Grid>
                
                {/* Легочный клапан */}
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" gutterBottom>
                    Клапан легочной артерии
                  </Typography>
                  <TextField
                    fullWidth
                    size="small"
                    label="Регургитация"
                    value={echoData.valves.pulmonary.regurgitation}
                    onChange={(e) => handleNestedChange('valves', 'pulmonary', 'regurgitation', e.target.value)}
                    placeholder="0-4 ст."
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Дополнительные параметры */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Дополнительные параметры
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Диастолическая функция"
                    value={echoData.diastolicFunction}
                    onChange={(e) => setEchoData(prev => ({ ...prev, diastolicFunction: e.target.value }))}
                    placeholder="Тип I, II, III"
                  />
                </Grid>
                
                <Grid item xs={12} md={6}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={echoData.pericardialEffusion}
                        onChange={(e) => setEchoData(prev => ({ ...prev, pericardialEffusion: e.target.checked }))}
                      />
                    }
                    label="Перикардиальный выпот"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Заключение */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Заключение
              </Typography>
              
              <TextField
                fullWidth
                multiline
                rows={4}
                value={echoData.conclusion}
                onChange={(e) => setEchoData(prev => ({ ...prev, conclusion: e.target.value }))}
                placeholder="Введите заключение по результатам ЭхоКГ..."
                sx={{ mb: 2 }}
              />
              
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Рекомендации"
                value={echoData.recommendations}
                onChange={(e) => setEchoData(prev => ({ ...prev, recommendations: e.target.value }))}
                placeholder="Рекомендации пациенту..."
              />
            </Paper>

            {/* AI результат */}
            {aiResult && !aiResult.error && (
              <Alert severity="info" sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  AI Интерпретация:
                </Typography>
                <Typography variant="body2">
                  {aiResult.interpretation}
                </Typography>
                {aiResult.alerts && aiResult.alerts.length > 0 && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" display="block" gutterBottom>
                      Важные находки:
                    </Typography>
                    {aiResult.alerts.map((alert, i) => (
                      <Chip
                        key={i}
                        size="small"
                        label={alert}
                        color="warning"
                        sx={{ mr: 1, mb: 0.5 }}
                      />
                    ))}
                  </Box>
                )}
              </Alert>
            )}

            {/* Кнопки действий */}
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
              <Button
                variant="outlined"
                startIcon={<AutoFixHigh />}
                onClick={analyzeWithAI}
                disabled={aiAnalyzing}
              >
                {aiAnalyzing ? 'Анализ...' : 'AI Интерпретация'}
              </Button>
              
              <Button
                variant="contained"
                startIcon={<Save />}
                onClick={saveEchoData}
                disabled={saving}
              >
                {saving ? 'Сохранение...' : saved ? 'Сохранено' : 'Сохранить'}
              </Button>
            </Box>
          </Collapse>
        </CardContent>
      </Card>
    </Box>
  );
};

export default EchoForm;

