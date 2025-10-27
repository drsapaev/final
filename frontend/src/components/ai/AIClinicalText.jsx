import React from 'react';
import {
  Box,
  Typography,
  Badge,
  Alert,
} from '../ui/macos';
import {
  Hospital,
  Info,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';

/**
 * Компонент для красивого отображения клинических рекомендаций AI
 * Парсит форматированный текст и отображает его с правильной структурой
 */
const AIClinicalText = ({ content, variant = 'info' }) => {
  if (!content) return null;

  // Разбираем контент на секции
  const parseContent = (text) => {
    const sections = [];
    let currentSection = null;

    const lines = text.split('\n');
    
    lines.forEach((line) => {
      // Заголовки с ### или **
      if (line.match(/^###\s+(.+)$/)) {
        if (currentSection) sections.push(currentSection);
        currentSection = {
          type: 'heading',
          content: line.replace(/^###\s+/, '').replace(/\*\*/g, ''),
          items: []
        };
      }
      // Диагнозы с >
      else if (line.match(/^>\s+(.+)$/)) {
        if (currentSection) {
          currentSection.items.push({
            type: 'diagnosis',
            content: line.replace(/^>\s+/, '')
          });
        }
      }
      // Пункты списка
      else if (line.match(/^-\s+(.+)$/) || line.match(/^\d+\.\s+(.+)$/)) {
        if (currentSection) {
          currentSection.items.push({
            type: 'list',
            content: line.replace(/^[-\d+.]\s+/, '')
          });
        }
      }
      // Эмодзи заголовки
      else if (line.match(/^(🩺|🧠|🧬|🧩|💡|📋)\s*\*\*(.+?)\*\*/)) {
        if (currentSection) currentSection.items.push({ type: 'break' });
        if (currentSection) {
          currentSection.items.push({
            type: 'subheading',
            content: line.replace(/\*\*/g, '').trim()
          });
        }
      }
      // Обычный текст
      else if (line.trim()) {
        if (currentSection) {
          currentSection.items.push({
            type: 'text',
            content: line.trim()
          });
        }
      }
    });

    if (currentSection) sections.push(currentSection);
    return sections;
  };

  const sections = parseContent(content);

  const renderItem = (item, idx) => {
    switch (item.type) {
      case 'diagnosis':
        return (
          <Alert 
            key={idx} 
            severity="success" 
            icon={<Hospital />}
            sx={{ my: 1 }}
          >
            <Typography variant="body1" fontWeight="bold">
              {item.content}
            </Typography>
          </Alert>
        );

      case 'subheading':
        return (
          <Box key={idx} sx={{ mt: 2, mb: 1 }}>
            <Typography variant="subtitle1" fontWeight="bold" color="primary">
              {item.content}
            </Typography>
          </Box>
        );

      case 'list':
        return (
          <Box key={idx} display="flex" alignItems="flex-start" gap={1} ml={2} my={0.5}>
            <CheckCircle fontSize="small" color="success" sx={{ mt: 0.5 }} />
            <Typography variant="body2">{item.content}</Typography>
          </Box>
        );

      case 'text':
        // Обнаруживаем специальные форматы
        if (item.content.includes('**')) {
          const parts = item.content.split(/\*\*(.+?)\*\*/);
          return (
            <Typography key={idx} variant="body2" paragraph>
              {parts.map((part, i) => 
                i % 2 === 1 ? <strong key={i}>{part}</strong> : part
              )}
            </Typography>
          );
        }
        
        // Обнаруживаем "Когда использовать:"
        if (item.content.startsWith('Когда использовать:')) {
          return (
            <Box key={idx} sx={{ ml: 2, mb: 1 }}>
              <Typography variant="body2" color="text.secondary">
                <Info fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                {item.content}
              </Typography>
            </Box>
          );
        }

        // Обнаруживаем "Формулировка:"
        if (item.content.startsWith('Формулировка:')) {
          return (
            <Paper key={idx} variant="outlined" sx={{ p: 1.5, ml: 2, mb: 1, bgcolor: 'action.hover' }}>
              <Typography variant="body2" fontStyle="italic">
                {item.content.replace('Формулировка:', '').trim()}
              </Typography>
            </Paper>
          );
        }

        return (
          <Typography key={idx} variant="body2" paragraph>
            {item.content}
          </Typography>
        );

      case 'break':
        return <Divider key={idx} sx={{ my: 2 }} />;

      default:
        return null;
    }
  };

  const getVariantColor = () => {
    switch (variant) {
      case 'success': return 'success.light';
      case 'warning': return 'warning.light';
      case 'error': return 'error.light';
      default: return 'info.light';
    }
  };

  return (
    <Paper 
      elevation={0} 
      sx={{ 
        p: 3, 
        bgcolor: getVariantColor(),
        border: 1,
        borderColor: 'divider'
      }}
    >
      {sections.map((section, sectionIdx) => (
        <Box key={sectionIdx} mb={sectionIdx < sections.length - 1 ? 3 : 0}>
          {/* Заголовок секции */}
          {section.type === 'heading' && (
            <Box mb={2}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                {section.content}
              </Typography>
              <Divider />
            </Box>
          )}

          {/* Элементы секции */}
          {section.items.map((item, itemIdx) => renderItem(item, itemIdx))}
        </Box>
      ))}
    </Paper>
  );
};

export default AIClinicalText;

