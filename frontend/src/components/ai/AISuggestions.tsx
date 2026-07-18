
import { useTranslation } from '../../i18n/useTranslation';
import { useState } from 'react';
import {
  Card, CardContent, Typography as TypographyRaw, Alert as AlertRaw, Badge, Button,
} from '../ui/macos';
import { Brain, Hospital, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { notify } from '../../services/notify';
import AIClinicalText from './AIClinicalText';
import PropTypes from 'prop-types';
import React from "react";
const Alert = AlertRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Typography = TypographyRaw as unknown as React.ComponentType<Record<string, unknown>>;

const AISuggestions = ({
  suggestions = [],
  type = 'icd10',
  onSelect,
  title,
  showConfidence = true,
  maxHeight = 400,
  clinicalRecommendations = null,
  fallbackProvider = null
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  title = title || t('misc.as_ai_podskazki');
  const [expanded, setExpanded] = useState(true);
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    notify.info(t('final.copied_to_clipboard'));
    setTimeout(() => setCopiedId(null), 2000);
  };
  const handleActivationKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
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
        padding: 'var(--mac-spacing-1) var(--mac-spacing-2)', borderRadius: 9999, fontSize: 12
      }}>{children}</span>);

  };


  Pill.propTypes = {
    ...(Pill.propTypes || {}),
    children: PropTypes.any,
    color: PropTypes.any,
  };

  const getRelevanceVariant = (relevance) => {
    switch ((relevance || '').toLowerCase()) {
      case t('misc.as_vysokaya'):
      case 'high':
        return 'success';
      case t('misc.as_srednyaya'):
      case 'medium':
        return 'warning';
      default:
        return 'default';
    }
  };

  const renderICD10Suggestions = () => {
    return (
      <div style={{ padding: 16 }}>
        {fallbackProvider &&
        <Alert severity="warning" style={{ marginBottom: 12 }}>
            Используется резервный провайдер: {fallbackProvider.toUpperCase()}
          </Alert>
        }
        {clinicalRecommendations &&
        <div style={{ marginBottom: 12 }}>
            <AIClinicalText content={clinicalRecommendations} variant="info" />
          </div>
        }
        {!suggestions || suggestions.length === 0 ?
        <Alert severity="info">{t('misc.as_net_podskazok_mkb_10')}</Alert> :

        <div style={{ maxHeight, overflow: 'auto' }}>
            {suggestions.map((item, index) =>
          <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--mac-spacing-3) 0', borderBottom: '1px solid var(--mac-border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Hospital style={{ color: 'var(--mac-accent-blue)' }} />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Typography variant="body2" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>{item.code}</Typography>
                      <Typography variant="body2" color="textSecondary">{item.name || item.description}</Typography>
                    </div>
                    {showConfidence && item.relevance &&
                <div style={{ marginTop: 4 }}>
                        <Pill color={getRelevanceVariant(item.relevance)}>{item.relevance}</Pill>
                      </div>
                }
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Button variant="outline" onClick={() => onSelect && onSelect(item)}>{t('misc.as_vybrat')}</Button>
                  <Button variant="outline" onClick={() => handleCopy(`${item.code} - ${item.name || item.description}`, index)}>
                    {copiedId === index ? <Check style={{ width: 14, height: 14, marginRight: 6 }} /> : <Copy style={{ width: 14, height: 14, marginRight: 6 }} />}
                    Копировать
                  </Button>
                </div>
              </div>
          )}
          </div>
        }
      </div>);

  };

  const renderGenericSuggestions = () => {
    if (!suggestions || suggestions.length === 0) {
      return <Alert severity="info">{t('misc.as_net_podskazok')}</Alert>;
    }
    return (
      <div style={{ maxHeight, overflow: 'auto', padding: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {suggestions.map((item, index) =>
        <Pill key={index} color="primary">
            <span
              role="button"
              tabIndex={0}
              onClick={() => onSelect && onSelect(item)}
              onKeyDown={(event) => handleActivationKeyDown(event, () => onSelect && onSelect(item))}
              style={{ cursor: 'pointer' }}>
              {typeof item === 'string' ? item : item.label || item.name || JSON.stringify(item)}
            </span>
            <button
              onClick={() => handleCopy(typeof item === 'string' ? item : item.label || item.name || JSON.stringify(item), index)}
              aria-label={t('misc.as_kopirovat_podskazku_ai')}
              style={{ marginLeft: 6, border: 'none', background: 'transparent', cursor: 'pointer' }}>
              {copiedId === index ? <Check style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
            </button>
          </Pill>
        )}
      </div>);

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
        <div
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
          role="button"
          tabIndex={0}
          onClick={() => setExpanded(!expanded)}
          onKeyDown={(event) => handleActivationKeyDown(event, () => setExpanded(!expanded))}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Brain style={{ color: 'var(--mac-accent-blue)' }} />
            <Typography variant="subtitle1" style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>{title}</Typography>
            {suggestions.length > 0 && <Badge variant="primary">{suggestions.length}</Badge>}
          </div>
          {expanded ? <ChevronUp /> : <ChevronDown />}
        </div>
        {expanded &&
        <div style={{ marginTop: 8 }}>
            {renderContent()}
          </div>
        }
      </CardContent>
    </Card>);

};


AISuggestions.propTypes = {
  ...(AISuggestions.propTypes || {}),
  clinicalRecommendations: PropTypes.any,
  fallbackProvider: PropTypes.any,
  maxHeight: PropTypes.any,
  onSelect: PropTypes.any,
  showConfidence: PropTypes.any,
  suggestions: PropTypes.any,
  title: PropTypes.any,
  type: PropTypes.any,
};

export default AISuggestions;
