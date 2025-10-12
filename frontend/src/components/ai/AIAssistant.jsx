import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Stack,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  ExpandMore,
  Psychology,
  Warning,
  CheckCircle,
  Info,
  ContentCopy,
  Refresh
} from '@mui/icons-material';
import { useSnackbar } from 'notistack';
import { apiClient } from '../../api/client';
import { mcpAPI } from '../../api/mcpClient';

const AIAssistant = ({ 
  analysisType, 
  data, 
  onResult,
  title = "AI Ассистент",
  expanded = true,
  useMCP = true,  // Использовать MCP по умолчанию
  providerOptions = ['deepseek', 'gemini', 'openai', 'default'] // Доступные AI провайдеры
}) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [provider, setProvider] = useState('deepseek'); // DeepSeek по умолчанию
  const [retryCount, setRetryCount] = useState(0);
  const { enqueueSnackbar } = useSnackbar();

  const analyzeData = async (manualRetry = false) => {
    setLoading(true);
    setError(null);
    if (!manualRetry) {
      setResult(null);
      setRetryCount(0);
    }

    try {
      let response;
      let mcpResult;

      switch (analysisType) {
        case 'complaint':
          if (useMCP) {
            mcpResult = await mcpAPI.analyzeComplaint({
              complaint: data.complaint,
              patientAge: data.patient_age,
              patientGender: data.patient_gender,
              provider: provider
            });
            
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP analysis failed');
            }
          } else {
            response = await apiClient.post('/api/v1/ai/complaint-to-plan', {
              ...data,
              provider,
              use_mcp: false
            });
          }
          break;

        case 'icd10':
          if (useMCP) {
            mcpResult = await mcpAPI.suggestICD10({
              symptoms: data.symptoms || [],
              diagnosis: data.diagnosis,
              specialty: data.specialty,
              provider: provider,
              maxSuggestions: data.maxSuggestions || 5
            });
            
            if (mcpResult.status === 'success') {
              // Поддержка нового формата с clinical_recommendations
              if (mcpResult.data.clinical_recommendations) {
                response = { data: mcpResult.data };
              } else if (mcpResult.data.suggestions) {
                response = { data: mcpResult.data.suggestions };
              } else {
                response = { data: [] };
              }
            } else {
              throw new Error(mcpResult.error || 'MCP ICD10 suggestion failed');
            }
          } else {
            response = await apiClient.post('/api/v1/ai/icd-suggest', {
              ...data,
              provider
            });
          }
          break;

        case 'lab':
          if (useMCP) {
            mcpResult = await mcpAPI.interpretLabResults({
              results: data.results || data.lab_results,
              patientAge: data.patient_age,
              patientGender: data.patient_gender,
              provider: provider,
              includeRecommendations: true
            });
            
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP lab interpretation failed');
            }
          } else {
            response = await apiClient.post('/api/v1/ai/lab-interpret', {
              ...data,
              provider
            });
          }
          break;

        case 'ecg':
          response = await apiClient.post('/api/v1/ai/ecg-interpret', {
            ...data,
            provider
          });
          break;

        case 'skin':
          if (useMCP && data.image) {
            mcpResult = await mcpAPI.analyzeSkinLesion(
              data.image,
              data.lesionInfo,
              data.patientHistory,
              provider
            );
            
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP skin analysis failed');
            }
          } else {
            const formData = new FormData();
            formData.append('image', data.image);
            if (data.metadata) {
              formData.append('metadata', JSON.stringify(data.metadata));
            }
            formData.append('provider', provider);
            response = await apiClient.post('/api/v1/ai/skin-analyze', formData, {
              headers: { 'Content-Type': 'multipart/form-data' }
            });
          }
          break;

        case 'imaging':
          if (useMCP && data.image) {
            mcpResult = await mcpAPI.analyzeImage(
              data.image,
              data.imageType || 'general',
              {
                modality: data.modality,
                clinicalContext: data.clinicalContext,
                provider: provider
              }
            );
            
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP imaging analysis failed');
            }
          } else {
            throw new Error('Imaging analysis requires MCP mode');
          }
          break;

        default:
          throw new Error('Неизвестный тип анализа');
      }

      setResult(response.data);
      if (onResult) {
        onResult(response.data);
      }
      enqueueSnackbar('AI анализ завершен', { variant: 'success' });
      setRetryCount(0);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message;
      setError(errorMsg);
      enqueueSnackbar(`Ошибка AI анализа: ${errorMsg}`, { variant: 'error' });
      setRetryCount(prev => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    enqueueSnackbar('Скопировано в буфер обмена', { variant: 'info' });
  };

  const renderComplaintResult = () => {
    if (!result) return null;

    return (
      <Box>
        {/* Предварительные диагнозы */}
        {result.preliminary_diagnosis && (
          <Box mb={2}>
            <Typography variant="subtitle2" gutterBottom>
              Предварительные диагнозы:
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {result.preliminary_diagnosis.map((diagnosis, idx) => (
                <Chip
                  key={idx}
                  label={diagnosis}
                  color="primary"
                  variant="outlined"
                  size="small"
                />
              ))}
            </Stack>
          </Box>
        )}

        {/* План обследований */}
        {result.examinations && result.examinations.length > 0 && (
          <Box mb={2}>
            <Typography variant="subtitle2" gutterBottom>
              План обследований:
            </Typography>
            <List dense>
              {result.examinations.map((exam, idx) => (
                <ListItem key={idx}>
                  <ListItemIcon>
                    <CheckCircle color="success" fontSize="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={`${exam.type}: ${exam.name}`}
                    secondary={exam.reason}
                  />
                </ListItem>
              ))}
            </List>
          </Box>
        )}

        {/* Лабораторные анализы */}
        {result.lab_tests && result.lab_tests.length > 0 && (
          <Box mb={2}>
            <Typography variant="subtitle2" gutterBottom>
              Лабораторные анализы:
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {result.lab_tests.map((test, idx) => (
                <Chip
                  key={idx}
                  label={test}
                  size="small"
                  variant="outlined"
                />
              ))}
            </Stack>
          </Box>
        )}

        {/* Тревожные симптомы */}
        {result.red_flags && result.red_flags.length > 0 && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Тревожные симптомы:
            </Typography>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {result.red_flags.map((flag, idx) => (
                <li key={idx}>{flag}</li>
              ))}
            </ul>
          </Alert>
        )}

        {/* Срочность */}
        {result.urgency && (
          <Box mt={2}>
            <Chip
              label={`Срочность: ${result.urgency}`}
              color={
                result.urgency === 'экстренно' ? 'error' :
                result.urgency === 'неотложно' ? 'warning' : 'info'
              }
            />
          </Box>
        )}
      </Box>
    );
  };

  const renderICD10Result = () => {
    // Поддержка нового формата с clinical_recommendations
    if (result && result.clinical_recommendations) {
      return (
        <Box>
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {result.clinical_recommendations}
            </Typography>
          </Alert>
          
          {result.suggestions && result.suggestions.length > 0 && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Коды МКБ-10:
              </Typography>
              <List>
                {result.suggestions.map((item, idx) => (
                  <ListItem
                    key={idx}
                    secondaryAction={
                      <IconButton
                        edge="end"
                        onClick={() => copyToClipboard(`${item.code} - ${item.name || item.description}`)}
                      >
                        <ContentCopy />
                      </IconButton>
                    }
                  >
                    <ListItemText
                      primary={`${item.code} - ${item.name || item.description}`}
                      secondary={
                        item.relevance && (
                          <Chip
                            label={item.relevance}
                            size="small"
                            color={
                              item.relevance === 'высокая' ? 'success' :
                              item.relevance === 'средняя' ? 'warning' : 'default'
                            }
                          />
                        )
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </Box>
      );
    }

    // Старый формат - простой массив кодов
    if (!result || !Array.isArray(result)) return null;

    return (
      <List>
        {result.map((item, idx) => (
          <ListItem
            key={idx}
            secondaryAction={
              <IconButton
                edge="end"
                onClick={() => copyToClipboard(`${item.code} - ${item.name || item.description}`)}
              >
                <ContentCopy />
              </IconButton>
            }
          >
            <ListItemText
              primary={`${item.code} - ${item.name || item.description}`}
              secondary={
                item.relevance && (
                  <Chip
                    label={item.relevance}
                    size="small"
                    color={
                      item.relevance === 'высокая' ? 'success' :
                      item.relevance === 'средняя' ? 'warning' : 'default'
                    }
                  />
                )
              }
            />
          </ListItem>
        ))}
      </List>
    );
  };

  const renderLabResult = () => {
    if (!result) return null;

    return (
      <Box>
        {/* Общее заключение */}
        {result.summary && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">{result.summary}</Typography>
          </Alert>
        )}

        {/* Отклонения от нормы */}
        {result.abnormal_values && result.abnormal_values.length > 0 && (
          <Box mb={2}>
            <Typography variant="subtitle2" gutterBottom>
              Отклонения от нормы:
            </Typography>
            {result.abnormal_values.map((item, idx) => (
              <Accordion key={idx} defaultExpanded={idx === 0}>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography>
                    {item.parameter}: {item.value}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box>
                    <Typography variant="body2" gutterBottom>
                      <strong>Интерпретация:</strong> {item.interpretation}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Клиническое значение:</strong> {item.clinical_significance}
                    </Typography>
                  </Box>
                </AccordionDetails>
              </Accordion>
            ))}
          </Box>
        )}

        {/* Возможные состояния */}
        {result.possible_conditions && result.possible_conditions.length > 0 && (
          <Box mb={2}>
            <Typography variant="subtitle2" gutterBottom>
              Возможные состояния:
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {result.possible_conditions.map((condition, idx) => (
                <Chip
                  key={idx}
                  label={condition}
                  color="warning"
                  variant="outlined"
                  size="small"
                />
              ))}
            </Stack>
          </Box>
        )}

        {/* Рекомендации */}
        {result.recommendations && result.recommendations.length > 0 && (
          <Box mb={2}>
            <Typography variant="subtitle2" gutterBottom>
              Рекомендации:
            </Typography>
            <List dense>
              {result.recommendations.map((rec, idx) => (
                <ListItem key={idx}>
                  <ListItemIcon>
                    <Info color="primary" fontSize="small" />
                  </ListItemIcon>
                  <ListItemText primary={rec} />
                </ListItem>
              ))}
            </List>
          </Box>
        )}

        {/* Срочность консультации */}
        {result.urgency && (
          <Alert 
            severity={result.urgency === 'да' ? 'warning' : 'info'}
            sx={{ mt: 2 }}
          >
            Срочная консультация: {result.urgency}
          </Alert>
        )}
      </Box>
    );
  };

  const renderECGResult = () => {
    if (!result) return null;

    return (
      <Box>
        <Stack spacing={2}>
          {/* Основные параметры */}
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Основные параметры:
            </Typography>
            <Stack spacing={1}>
              {result.rhythm && (
                <Typography variant="body2">
                  <strong>Ритм:</strong> {result.rhythm}
                </Typography>
              )}
              {result.rate && (
                <Typography variant="body2">
                  <strong>ЧСС:</strong> {result.rate}
                </Typography>
              )}
              {result.conduction && (
                <Typography variant="body2">
                  <strong>Проводимость:</strong> {result.conduction}
                </Typography>
              )}
              {result.axis && (
                <Typography variant="body2">
                  <strong>Электрическая ось:</strong> {result.axis}
                </Typography>
              )}
            </Stack>
          </Paper>

          {/* Выявленные отклонения */}
          {result.abnormalities && result.abnormalities.length > 0 && (
            <Alert severity="warning">
              <Typography variant="subtitle2" gutterBottom>
                Выявленные отклонения:
              </Typography>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {result.abnormalities.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </Alert>
          )}

          {/* Заключение */}
          {result.interpretation && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Заключение:
              </Typography>
              <Typography variant="body2">{result.interpretation}</Typography>
            </Paper>
          )}

          {/* Рекомендации */}
          {result.recommendations && result.recommendations.length > 0 && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Рекомендации:
              </Typography>
              <List dense>
                {result.recommendations.map((rec, idx) => (
                  <ListItem key={idx}>
                    <ListItemIcon>
                      <CheckCircle color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary={rec} />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          {/* Срочность */}
          {result.urgency && (
            <Chip
              label={`Консультация кардиолога: ${result.urgency}`}
              color={
                result.urgency === 'экстренно' ? 'error' :
                result.urgency === 'планово' ? 'info' : 'default'
              }
            />
          )}
        </Stack>
      </Box>
    );
  };

  const renderResult = () => {
    if (error) {
      return (
        <Alert severity="error">
          {error}
        </Alert>
      );
    }

    if (!result) return null;

    switch (analysisType) {
      case 'complaint':
        return renderComplaintResult();
      case 'icd10':
        return renderICD10Result();
      case 'lab':
        return renderLabResult();
      case 'ecg':
        return renderECGResult();
      default:
        return (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </Paper>
        );
    }
  };

  return (
    <Paper elevation={1} sx={{ p: 2 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Box display="flex" alignItems="center" gap={1}>
          <Psychology color="primary" />
          <Typography variant="h6">{title}</Typography>
          {useMCP && (
            <Chip label="MCP" size="small" color="success" variant="outlined" />
          )}
        </Box>
        <Box display="flex" alignItems="center" gap={1}>
          {/* Выбор AI провайдера */}
          <Stack direction="row" spacing={0.5}>
            {providerOptions.map((prov) => (
              <Chip
                key={prov}
                label={prov.toUpperCase()}
                size="small"
                color={provider === prov ? 'primary' : 'default'}
                variant={provider === prov ? 'filled' : 'outlined'}
                onClick={() => setProvider(prov)}
                disabled={loading}
              />
            ))}
          </Stack>
          
          <Tooltip title="Повторить анализ">
            <IconButton 
              onClick={() => analyzeData(true)} 
              disabled={loading || !data}
              size="small"
            >
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {loading ? (
        <Box display="flex" flexDirection="column" alignItems="center" p={4}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Анализ через {provider.toUpperCase()} AI...
          </Typography>
        </Box>
      ) : (
        renderResult()
      )}

      {!result && !loading && !error && (
        <Alert severity="info">
          Нажмите кнопку обновления для запуска AI анализа
        </Alert>
      )}
      
      {error && retryCount > 0 && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          <Typography variant="body2">
            Попытка {retryCount}. Попробуйте сменить AI провайдер или повторить запрос.
          </Typography>
        </Alert>
      )}
    </Paper>
  );
};

export default AIAssistant;

