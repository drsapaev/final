import React from 'react';
import { useState } from 'react';
import { Box, Card, CardContent, Typography, Alert, Badge, Button } from '../../components/ui/macos';
import { Brain, Hospital, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { useSnackbar } from 'notistack';
import AIClinicalText from './AIClinicalText';

const AISuggestions = ({ 
  suggestions = [], 
  type = 'icd10',
  onSelect,
  title = 'AI Подсказки',
  showConfidence = true,
  maxHeight = 400,
  clinicalRecommendations = null,
  fallbackProvider = null
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

  const Pill = ({ children, color = 'default' }) => {
    const colors = {
      default: { border: 'var(--mac-border)', bg: 'transparent' },
      primary: { border: 'var(--mac-accent-blue)', bg: 'rgba(0,122,255,0.08)' },
      success: { border: 'rgba(52,199,89,0.45)', bg: 'rgba(52,199,89,0.08)' },
      warning: { border: 'rgba(255,149,0,0.45)', bg: 'rgba(255,149,0,0.08)' }
    }[color] || {};
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        border: `1px solid ${colors.border}`,
        background: colors.bg,
        padding: '4px 8px', borderRadius: 9999, fontSize: 12
      }}>{children}</span>
    );
  };

  const getRelevanceVariant = (relevance) => {
    switch ((relevance || '').toLowerCase()) {
      case 'высокая':
      case 'high':
        return 'success';
      case 'средняя':
      case 'medium':
        return 'warning';
      default:
        return 'default';
    }
  };

  const renderICD10Suggestions = () => {
    return (
      <div style={{ padding: 16 }}>
        {fallbackProvider && (
          <Alert severity="warning" style={{ marginBottom: 12 }}>
            Используется резервный провайдер: {fallbackProvider.toUpperCase()}
          </Alert>
        )}
        {clinicalRecommendations && (
          <div style={{ marginBottom: 12 }}>
            <AIClinicalText content={clinicalRecommendations} variant="info" />
          </div>
        )}
        {(!suggestions || suggestions.length === 0) ? (
          <Alert severity="info">Нет подсказок МКБ-10</Alert>
        ) : (
          <div style={{ maxHeight, overflow: 'auto' }}>
            {suggestions.map((item, index) => (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--mac-border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Hospital style={{ color: 'var(--mac-accent-blue)' }} />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Typography variant="body2" style={{ fontWeight: 600 }}>{item.code}</Typography>
                      <Typography variant="body2" color="textSecondary">{item.name || item.description}</Typography>
                    </div>
                    {showConfidence && item.relevance && (
                      <div style={{ marginTop: 4 }}>
                        <Pill color={getRelevanceVariant(item.relevance)}>{item.relevance}</Pill>
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Button variant="outline" onClick={() => onSelect && onSelect(item)}>Выбрать</Button>
                  <Button variant="outline" onClick={() => handleCopy(`${item.code} - ${item.name || item.description}`, index)}>
                    {copiedId === index ? <Check style={{ width: 14, height: 14, marginRight: 6 }} /> : <Copy style={{ width: 14, height: 14, marginRight: 6 }} />}
                    Копировать
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderGenericSuggestions = () => {
    if (!suggestions || suggestions.length === 0) {
      return <Alert severity="info">Нет подсказок</Alert>;
    }
    return (
      <div style={{ maxHeight, overflow: 'auto', padding: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {suggestions.map((item, index) => (
          <Pill key={index} color="primary">
            <span onClick={() => onSelect && onSelect(item)} style={{ cursor: 'pointer' }}>
              {typeof item === 'string' ? item : item.label || item.name || JSON.stringify(item)}
            </span>
            <button onClick={() => handleCopy(typeof item === 'string' ? item : item.label || item.name || JSON.stringify(item), index)} style={{ marginLeft: 6, border: 'none', background: 'transparent', cursor: 'pointer' }}>
              {copiedId === index ? <Check style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
            </button>
          </Pill>
        ))}
      </div>
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
    <Card>
      <CardContent>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }} onClick={() => setExpanded(!expanded)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Brain style={{ color: 'var(--mac-accent-blue)' }} />
            <Typography variant="subtitle1" style={{ fontWeight: 500 }}>{title}</Typography>
            {suggestions.length > 0 && (<Badge variant="primary">{suggestions.length}</Badge>)}
          </div>
          {expanded ? <ChevronUp /> : <ChevronDown />}
        </div>
        {expanded && (
          <div style={{ marginTop: 8 }}>
            {renderContent()}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AISuggestions;

