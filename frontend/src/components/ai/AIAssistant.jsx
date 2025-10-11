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
  useMCP = true  // Использовать MCP по умолчанию
}) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [provider, setProvider] = useState('default');
  const { enqueueSnackbar } = useSnackbar();

  const analyzeData = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let response;
      const config = { provider };

      switch (analysisType) {
        case 'complaint':
          if (useMCP) {
            // Используем MCP для анализа жалоб
            const mcpResult = await mcpAPI.analyzeComplaint({
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
            // Используем прямой API
            response = await apiClient.post('/api/v1/ai/complaint-to-plan', {
              ...data,
              ...config,
              use_mcp: false
            });
          }
          break;

        case 'icd10':
          response = await apiClient.post('/api/v1/ai/icd-suggest', {
            ...data,
            ...config
          });
          break;

        case 'lab':
          response = await apiClient.post('/api/v1/ai/lab-interpret', {
            ...data,
            ...config
          });
          break;

        case 'ecg':
          response = await apiClient.post('/api/v1/ai/ecg-interpret', {
            ...data,
            ...config
          });
          break;

        case 'skin':
          const formData = new FormData();
          formData.append('image', data.image);
          if (data.metadata) {
            formData.append('metadata', JSON.stringify(data.metadata));
          }
          if (config.provider) {
            formData.append('provider', config.provider);
          }
          response = await apiClient.post('/api/v1/ai/skin-analyze', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
          });
          break;

        default:
          throw new Error('Неизвестный тип анализа');
      }

      setResult(response.data);
      if (onResult) {
        onResult(response.data);
      }
      enqueueSnackbar('AI анализ завершен', { variant: 'success' });
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      enqueueSnackbar('Ошибка AI анализа', { variant: 'error' });
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
    if (!result || !Array.isArray(result)) return null;

    return (
      <List>
        {result.map((item, idx) => (
          <ListItem
            key={idx}
            secondaryAction={
              <IconButton
                edge="end"
                onClick={() => copyToClipboard(`${item.code} - ${item.name}`)}
              >
                <ContentCopy />
              </IconButton>
            }
          >
            <ListItemText
              primary={`${item.code} - ${item.name}`}
              secondary={
                <Chip
                  label={item.relevance}
                  size="small"
                  color={
                    item.relevance === 'высокая' ? 'success' :
                    item.relevance === 'средняя' ? 'warning' : 'default'
                  }
                />
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
        </Box>
        <Box>
          <Tooltip title="Повторить анализ">
            <IconButton 
              onClick={analyzeData} 
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
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : (
        renderResult()
      )}

      {!result && !loading && !error && (
        <Alert severity="info">
          Нажмите кнопку обновления для запуска AI анализа
        </Alert>
      )}
    </Paper>
  );
};

export default AIAssistant;

