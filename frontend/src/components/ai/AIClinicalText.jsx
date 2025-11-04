import React from 'react';
import {
  Box,
  Typography,
  Badge,
  Alert,
  Paper,
} from '../ui/macos';
import { Divider } from '../ui/macos/List';
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
            style={{ marginTop: '8px', marginBottom: '8px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Hospital size={18} />
              <Typography variant="body1" style={{ fontWeight: 'bold' }}>
                {item.content}
              </Typography>
            </div>
          </Alert>
        );

      case 'subheading':
        return (
          <Box key={idx} mt={2} mb={1}>
            <Typography variant="subtitle1" style={{ fontWeight: 'bold', color: 'var(--mac-accent-blue)' }}>
              {item.content}
            </Typography>
          </Box>
        );

      case 'list':
        return (
          <Box key={idx} display="flex" alignItems="flex-start" gap={1} style={{ marginLeft: '16px', marginTop: '4px', marginBottom: '4px' }}>
            <CheckCircle size={16} style={{ marginTop: '4px', color: 'var(--mac-success)' }} />
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
            <Box key={idx} style={{ marginLeft: '16px', marginBottom: '8px' }}>
              <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)' }}>
                <Info size={16} style={{ verticalAlign: 'middle', marginRight: '4px', display: 'inline-block' }} />
                {item.content}
              </Typography>
            </Box>
          );
        }

        // Обнаруживаем "Формулировка:"
        if (item.content.startsWith('Формулировка:')) {
          return (
            <Paper key={idx} variant="outlined" style={{ padding: '12px', marginLeft: '16px', marginBottom: '8px', backgroundColor: 'var(--mac-bg-secondary)' }}>
              <Typography variant="body2" style={{ fontStyle: 'italic' }}>
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
        return <Divider key={idx} style={{ marginTop: '16px', marginBottom: '16px' }} />;

      default:
        return null;
    }
  };


  const variantBgColor = {
    'success': 'var(--mac-success)',
    'warning': 'var(--mac-warning)', 
    'error': 'var(--mac-error)',
    'info': 'var(--mac-info)'
  }[variant] || 'var(--mac-bg-primary)';

  return (
    <Paper 
      elevation={0} 
      style={{ 
        padding: '24px', 
        backgroundColor: variantBgColor,
        border: '1px solid var(--mac-border)',
        borderRadius: '8px'
      }}
    >
      {sections.map((section, sectionIdx) => (
        <Box key={sectionIdx} mb={sectionIdx < sections.length - 1 ? 3 : 0}>
          {/* Заголовок секции */}
          {section.type === 'heading' && (
            <Box mb={2}>
              <Typography variant="h6" style={{ fontWeight: 'bold', marginBottom: '8px' }}>
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

