import {
  Box,
  Typography,
  Alert,
  Paper,
} from '../ui/macos';
// UX Audit Registrar #1: P6 codemod в PR #1898 случайно заменил
// `from '../ui/macos/List'` на `from '../ui/macos'`. Но `Divider`
// экспортируется только из ./List, не из barrel-export. Возвращаем прямой путь.
import { Divider } from '../ui/macos/List';
import {
  Hospital,
  Info,

  CheckCircle } from
'lucide-react';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/adapter';

/**
 * Компонент для красивого отображения клинических рекомендаций AI
 * Парсит форматированный текст и отображает его с правильной структурой
 */
const AIClinicalText = ({ content, variant = 'info' }) => {
  const { t } = useTranslation();
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
            style={{ marginTop: 'var(--mac-spacing-2)', marginBottom: 'var(--mac-spacing-2)' }}>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
              <Hospital size={18} />
              <Typography variant="body1" style={{ fontWeight: 'var(--mac-font-weight-bold)' }}>
                {item.content}
              </Typography>
            </div>
          </Alert>);


      case 'subheading':
        return (
          <Box key={idx} mt={2} mb={1}>
            <Typography variant="subtitle1" style={{ fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-accent-blue)' }}>
              {item.content}
            </Typography>
          </Box>);


      case 'list':
        return (
          <Box key={idx} display="flex" alignItems="flex-start" gap={1} style={{ marginLeft: 'var(--mac-spacing-4)', marginTop: 'var(--mac-spacing-1)', marginBottom: 'var(--mac-spacing-1)' }}>
            <CheckCircle size={16} style={{ marginTop: 'var(--mac-spacing-1)', color: 'var(--mac-success)' }} />
            <Typography variant="body2">{item.content}</Typography>
          </Box>);


      case 'text':
        // Обнаруживаем специальные форматы
        if (item.content.includes('**')) {
          const parts = item.content.split(/\*\*(.+?)\*\*/);
          return (
            <Typography key={idx} variant="body2" paragraph>
              {parts.map((part, i) =>
              i % 2 === 1 ? <strong key={i}>{part}</strong> : part
              )}
            </Typography>);

        }

        // Обнаруживаем "Когда использовать:"
        if (item.content.startsWith('Когда использовать:')) {
          return (
            <Box key={idx} style={{ marginLeft: 'var(--mac-spacing-4)', marginBottom: 'var(--mac-spacing-2)' }}>
              <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)' }}>
                <Info size={16} style={{ verticalAlign: 'middle', marginRight: 'var(--mac-spacing-1)', display: 'inline-block' }} />
                {item.content}
              </Typography>
            </Box>);

        }

        // Обнаруживаем "Формулировка:"
        if (item.content.startsWith('Формулировка:')) {
          return (
            <Paper key={idx} variant="outlined" style={{ padding: 'var(--mac-spacing-3)', marginLeft: 'var(--mac-spacing-4)', marginBottom: 'var(--mac-spacing-2)', backgroundColor: 'var(--mac-bg-secondary)' }}>
              <Typography variant="body2" style={{ fontStyle: 'italic' }}>
                {item.content.replace('Формулировка:', '').trim()}
              </Typography>
            </Paper>);

        }

        return (
          <Typography key={idx} variant="body2" paragraph>
            {item.content}
          </Typography>);


      case 'break':
        return <Divider key={idx} style={{ marginTop: 'var(--mac-spacing-4)', marginBottom: 'var(--mac-spacing-4)' }} />;

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
        padding: 'var(--mac-spacing-6)',
        backgroundColor: variantBgColor,
        border: '1px solid var(--mac-border)',
        borderRadius: 'var(--mac-radius-md)'
      }}>
      
      {sections.map((section, sectionIdx) =>
      <Box key={sectionIdx} mb={sectionIdx < sections.length - 1 ? 3 : 0}>
          {/* Заголовок секции */}
          {section.type === 'heading' &&
        <Box mb={2}>
              <Typography variant="h6" style={{ fontWeight: 'var(--mac-font-weight-bold)', marginBottom: 'var(--mac-spacing-2)' }}>
                {section.content}
              </Typography>
              <Divider />
            </Box>
        }

          {/* Элементы секции */}
          {section.items.map((item, itemIdx) => renderItem(item, itemIdx))}
        </Box>
      )}
    </Paper>);

};


AIClinicalText.propTypes = {
  ...(AIClinicalText.propTypes || {}),
  content: PropTypes.any,
  variant: PropTypes.any,
};

export default AIClinicalText;