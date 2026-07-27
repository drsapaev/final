
import { useTranslation } from '../../i18n/useTranslation';
import { useState } from 'react';
import {
  Card, CardContent, Typography, Alert, Badge, Button,
} from '../ui/macos';
import { Brain, Hospital, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { notify } from '../../services/notify';
import AIClinicalText from './AIClinicalText';
import PropTypes from 'prop-types';
import React from "react";

interface ICD10Suggestion {
  code?: string;
  name?: string;
  description?: string;
  relevance?: string;
  [key: string]: unknown;
}

interface GenericSuggestion {
  label?: string;
  name?: string;
  [key: string]: unknown;
}

type Suggestion = ICD10Suggestion | GenericSuggestion | string;

interface AISuggestionsProps {
  suggestions?: Suggestion[];
  type?: string;
  onSelect?: (item: Suggestion) => void;
  title?: string;
  showConfidence?: boolean;
  maxHeight?: number;
  clinicalRecommendations?: string | null;
  fallbackProvider?: string | null;
}

const AISuggestions = ({
  suggestions = [],
  type = 'icd10',
  onSelect,
  title,
  showConfidence = true,
  maxHeight = 400,
  clinicalRecommendations = null,
  fallbackProvider = null
}: AISuggestionsProps) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  title = title || t('misc.as_ai_podskazki');
  const [expanded, setExpanded] = useState(true);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const handleCopy = (text: string, id: number) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    notify.info(t('final.copied_to_clipboard'));
    setTimeout(() => setCopiedId(null), 2000);
  };
  const handleActivationKeyDown = (event: React.KeyboardEvent<HTMLElement>, onActivate: () => void) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };

  const Pill = ({ children, color = 'default' }: { children: React.ReactNode; color?: string }) => {
    const colors = ((): { border?: string; bg?: string } => {
      const map: Record<string, { border: string; bg: string }> = {
        default: { border: 'var(--mac-border)', bg: 'transparent' },
        primary: { border: 'var(--mac-accent-blue)', bg: 'rgba(0,122,255,0.08)' },
        success: { border: 'rgba(52,199,89,0.45)', bg: 'rgba(52,199,89,0.08)' },
        warning: { border: 'rgba(255,149,0,0.45)', bg: 'rgba(255,149,0,0.08)' }
      };
      return map[color || 'default'] || {};
    })();
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        border: `1px solid ${colors.border}`,
        background: colors.bg,
        padding: 'var(--mac-spacing-1) var(--mac-spacing-2)', borderRadius: 9999, fontSize: 12
      }}>{children}</span>);

  };


  // audit/strict: removed self-referencing propTypes spread
Pill.propTypes = {
    children: PropTypes.any,
    color: PropTypes.any,
  };

  const getRelevanceVariant = (relevance: string | undefined): string => {
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
            {suggestions.map((item, index) => {
              const icd = typeof item === 'object' ? item as ICD10Suggestion : null;
              return (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--mac-spacing-3) 0', borderBottom: '1px solid var(--mac-border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Hospital style={{ color: 'var(--mac-accent-blue)' }} />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Typography variant="body2" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>{icd?.code}</Typography>
                      <Typography variant="body2" color="textSecondary">{icd?.name || icd?.description}</Typography>
                    </div>
                    {showConfidence && icd?.relevance &&
                <div style={{ marginTop: 4 }}>
                        <Pill color={getRelevanceVariant(icd?.relevance)}>{icd?.relevance}</Pill>
                      </div>
                }
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Button variant="outline" onClick={() => onSelect && onSelect(item)}>{t('misc.as_vybrat')}</Button>
                  <Button variant="outline" onClick={() => handleCopy(`${icd?.code} - ${icd?.name || icd?.description}`, index)}>
                    {copiedId === index ? <Check style={{ width: 14, height: 14, marginRight: 6 }} /> : <Copy style={{ width: 14, height: 14, marginRight: 6 }} />}
                    Копировать
                  </Button>
                </div>
              </div>
              );
            })}
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
        {suggestions.map((item, index) => {
          const text = typeof item === 'string'
            ? item
            : (item as GenericSuggestion).label || (item as GenericSuggestion).name || JSON.stringify(item);
          return (
        <Pill key={index} color="primary">
            <span
              role="button"
              tabIndex={0}
              onClick={() => onSelect && onSelect(item)}
              onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleActivationKeyDown(event, () => onSelect && onSelect(item))}
              style={{ cursor: 'pointer' }}>
              {text}
            </span>
            <button
              onClick={() => handleCopy(text, index)}
              aria-label={t('misc.as_kopirovat_podskazku_ai')}
              style={{ marginLeft: 6, border: 'none', background: 'transparent', cursor: 'pointer' }}>
              {copiedId === index ? <Check style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
            </button>
          </Pill>
          );
        })}
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
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleActivationKeyDown(event, () => setExpanded(!expanded))}>
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


// audit/strict: removed self-referencing propTypes spread
AISuggestions.propTypes = {
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
