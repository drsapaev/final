import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Stack,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Divider,
  IconButton,
  Collapse,
  Alert
} from '@mui/material';
import {
  Psychology,
  LocalHospital,
  ExpandMore,
  ExpandLess,
  ContentCopy,
  Check
} from '@mui/icons-material';
import { useState } from 'react';
import { useSnackbar } from 'notistack';
import AIClinicalText from './AIClinicalText';

const AISuggestions = ({ 
  suggestions = [], 
  type = 'icd10',
  onSelect,
  title = 'AI Подсказки',
  showConfidence = true,
  maxHeight = 400,
  clinicalRecommendations = null, // Новый формат клинических рекомендаций
  fallbackProvider = null // Провайдер, используемый при fallback
}) => {
  const [expanded, setExpanded] = useState(true);
  const [copiedId, setCopiedId] = useState(null);
  const { enqueueSnackbar } = useSnackbar();

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    enqueueSnackbar('Скопировано в буфер обмена', { variant: 'info' });
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getRelevanceColor = (relevance) => {
    switch (relevance?.toLowerCase()) {
      case 'высокая':
      case 'high':
        return 'success';
      case 'средняя':
      case 'medium':
        return 'warning';
      case 'низкая':
      case 'low':
        return 'default';
      default:
        return 'default';
    }
  };

  const renderICD10Suggestions = () => {
    return (
      <Box sx={{ p: 2 }}>
        {/* Показываем fallback провайдер если используется */}
        {fallbackProvider && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Используется резервный провайдер: {fallbackProvider.toUpperCase()}
          </Alert>
        )}

        {/* Клинические рекомендации (новый формат) */}
        {clinicalRecommendations && (
          <Box mb={3}>
            <AIClinicalText content={clinicalRecommendations} variant="info" />
          </Box>
        )}

        {/* Список кодов МКБ-10 */}
        {(!suggestions || suggestions.length === 0) ? (
          <Alert severity="info">
            Нет подсказок МКБ-10
          </Alert>
        ) : (
          <List dense sx={{ maxHeight, overflow: 'auto' }}>
            {suggestions.map((item, index) => (
              <ListItem
                key={index}
                disablePadding
                secondaryAction={
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => handleCopy(`${item.code} - ${item.name || item.description}`, index)}
                  >
                    {copiedId === index ? <Check color="success" /> : <ContentCopy />}
                  </IconButton>
                }
              >
                <ListItemButton onClick={() => onSelect && onSelect(item)}>
                  <ListItemIcon>
                    <LocalHospital color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="body2" fontWeight="bold">
                          {item.code}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {item.name || item.description}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      showConfidence && item.relevance && (
                        <Chip
                          label={item.relevance}
                          size="small"
                          color={getRelevanceColor(item.relevance)}
                          sx={{ mt: 0.5 }}
                        />
                      )
                    }
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        )}
      </Box>
    );
  };

  const renderGenericSuggestions = () => {
    if (!suggestions || suggestions.length === 0) {
      return (
        <Alert severity="info">
          Нет подсказок
        </Alert>
      );
    }

    return (
      <Stack spacing={1} sx={{ maxHeight, overflow: 'auto', p: 1 }}>
        {suggestions.map((item, index) => (
          <Chip
            key={index}
            label={typeof item === 'string' ? item : item.label || item.name || JSON.stringify(item)}
            onClick={() => onSelect && onSelect(item)}
            onDelete={() => handleCopy(
              typeof item === 'string' ? item : item.label || item.name || JSON.stringify(item),
              index
            )}
            deleteIcon={copiedId === index ? <Check /> : <ContentCopy />}
            color="primary"
            variant="outlined"
          />
        ))}
      </Stack>
    );
  };

  const renderContent = () => {
    switch (type) {
      case 'icd10':
        return renderICD10Suggestions();
      default:
        return renderGenericSuggestions();
    }
  };

  return (
    <Paper elevation={1} sx={{ overflow: 'hidden' }}>
      <Box
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        p={2}
        sx={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box display="flex" alignItems="center" gap={1}>
          <Psychology color="primary" />
          <Typography variant="subtitle1" fontWeight="medium">
            {title}
          </Typography>
          {suggestions.length > 0 && (
            <Chip
              label={suggestions.length}
              size="small"
              color="primary"
            />
          )}
        </Box>
        <IconButton size="small">
          {expanded ? <ExpandLess /> : <ExpandMore />}
        </IconButton>
      </Box>

      <Divider />

      <Collapse in={expanded}>
        <Box>
          {renderContent()}
        </Box>
      </Collapse>
    </Paper>
  );
};

export default AISuggestions;

