/**
 * TreatmentSection v2 - Лечение с шаблонами
 * 
 * Sources:
 * - 📜 Мой опыт (по диагнозу) - doctor's own treatment patterns
 * - 📋 Шаблоны - generic templates by specialty
 * - 🧠 AI - AI suggestions (requires complaints)
 * 
 * RULES:
 * - Templates insert only on click
 * - Through onChange → reducer
 * - 1 insert = 1 undo
 */

import PropTypes from 'prop-types';
import { useState, useCallback, useMemo } from 'react';
import { History, Pin, Edit2 } from 'lucide-react';
import EMRSection from './EMRSection';
import EMRSmartFieldV2 from './EMRSmartFieldV2';
import { TreatmentTemplatesButton, TreatmentTemplatesPanel } from '../templates';
import PrescriptionEditor from '../../emr/PrescriptionEditor';
import { useDoctorPhrases } from '../../../hooks/useDoctorPhrases';
import { useDoctorTreatmentTemplates } from '../../../hooks/useDoctorTreatmentTemplates';
import logger from '../../../utils/logger';

/**
 * TreatmentSection Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler (value, metadata?)
 * @param {Array} props.medications - Structured medications
 * @param {Function} props.onMedicationsChange - Change handler for meds
 * @param {boolean} props.disabled - Read-only mode (signed EMR)
 * @param {boolean} props.defaultOpen - Start expanded
 * @param {string} props.specialty - Doctor specialty for templates
 * @param {string} props.icd10Code - Current ICD-10 code for personalized templates
 */
export function TreatmentSection({
  value = '',
  onChange,
  medications = [],
  onMedicationsChange,
  disabled = false,
  defaultOpen = true,
  specialty = 'general',
  icd10Code = '', // for personalized templates
  complaints = '', // NEW: for AI availability check
  // AI Props
  suggestions = [],
  aiLoading = false,
  onApplySuggestion,
  onDismissSuggestion,
  onRequestAI,
  doctorId,
  experimentalGhostMode = false,
  onTelemetry
}) {
  const [showTemplates, setShowTemplates] = useState(false);
  const [showMyExperience, setShowMyExperience] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [editText, setEditText] = useState('');

  // 📜 Doctor's personal treatment patterns by ICD-10
  const {
    templates: myExperienceTemplates,
    loading: myExpLoading,
    hasTemplates: hasMyExperience,
    pinTemplate,
    unpinTemplate,
    updateTemplate
  } = useDoctorTreatmentTemplates({
    icd10Code,
    enabled: !!icd10Code && !!doctorId
  });

  // 🧠 Connect Doctor History (phrase-level)
  const { suggestions: doctorSuggestions, loading: historyLoading } = useDoctorPhrases({
    doctorId,
    field: 'treatment',
    specialty,
    currentText: value,
    config: { minQueryLength: 2 }
  });

  // Merge suggestions: history first, then AI
  const allSuggestions = useMemo(() => {
    const historyItems = doctorSuggestions.map((s) => ({
      id: s.id,
      content: s.text,
      source: 'history',
      confidence: 1.0
    }));
    return [...historyItems, ...suggestions];
  }, [doctorSuggestions, suggestions]);

  // ⚠️ AI доступен только если есть жалобы
  const aiEnabled = Boolean(complaints && complaints.trim().length > 0);

  // Handle AI request - only if complaints exist
  const handleRequestAI = useCallback((fieldName) => {
    if (!aiEnabled) {
      logger.log('[TreatmentSection] AI disabled - no complaints');
      return;
    }
    onRequestAI?.(fieldName);
  }, [aiEnabled, onRequestAI]);

  // Handle template apply (generic)
  const handleApplyTemplate = useCallback((newValue, templateId) => {
    onChange?.(newValue, {
      source: 'template',
      templateId
    });
  }, [onChange]);

  // Handle "My Experience" template apply
  const handleApplyMyExperience = useCallback((template) => {
    onChange?.(template.treatment_text, {
      source: 'my_experience',
      templateId: template.id,
      icd10Code: template.icd10_code
    });
    setShowMyExperience(false);
    onTelemetry?.({ type: 'treatment.my_experience.applied', payload: { icd10: template.icd10_code } });
  }, [onChange, onTelemetry]);

  return (
    <EMRSection
      title="Лечение"
      icon="💊"
      disabled={disabled}
      defaultOpen={defaultOpen}
      headerAction={
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {/* My Experience button - always visible */}
                    <button
          type="button"
          onClick={() => setShowMyExperience(true)}
          disabled={disabled || myExpLoading}
          className="btn btn-my-experience"
          title={hasMyExperience ?
          `Мой опыт${icd10Code ? ` по ${icd10Code}` : ''}` :
          'Нет сохранённых шаблонов'
          }
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 10px',
            fontSize: '12px',
            fontWeight: 500,
            background: hasMyExperience ?
            'var(--my-experience-bg, rgba(34, 197, 94, 0.15))' :
            'var(--surface-input, #252540)',
            border: hasMyExperience ?
            '1px solid var(--my-experience-border, #22c55e)' :
            '1px solid var(--border-default, rgba(255,255,255,0.1))',
            borderRadius: 'var(--radius-md, 6px)',
            color: hasMyExperience ?
            'var(--my-experience-text, #a7f3d0)' :
            'var(--text-secondary, #a8adb8)',
            cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.5 : 1,
            transition: 'all 0.15s ease'
          }}>
          
                        <History size={14} />
                        Мой опыт {hasMyExperience && `(${myExperienceTemplates.length})`}
                    </button>
                    {/* 📋 Generic Templates */}
                    <TreatmentTemplatesButton
          onClick={() => setShowTemplates(true)}
          disabled={disabled} />
        
                </div>
      }>
      
            <EMRSmartFieldV2
        value={value}
        onChange={onChange}
        placeholder="План лечения, назначения..."
        multiline
        rows={4}
        disabled={disabled}
        id="emr-treatment"
        fieldName="treatment"
        suggestions={allSuggestions}
        aiLoading={aiLoading || historyLoading}
        onApplySuggestion={onApplySuggestion}
        onDismissSuggestion={onDismissSuggestion}
        onRequestAI={aiEnabled ? handleRequestAI : null}
        showAIButton={aiEnabled}
        experimentalGhostMode={experimentalGhostMode}
        onTelemetry={onTelemetry} />
      

            {/* Structured Prescriptions */}
            <div style={{ marginTop: '16px' }}>
                <h4 style={{ fontSize: '13px', fontWeight: 600, color: '#666', marginBottom: '8px' }}>
                    Лекарственные назначения
                </h4>
                <PrescriptionEditor
          prescriptions={medications || []}
          onChange={onMedicationsChange}
          isEditable={!disabled} />
        
            </div>

            {/* 📜 My Experience Panel */}
            {showMyExperience &&
      <div
        style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}
        role="button"
        tabIndex={0}
        onClick={() => setShowMyExperience(false)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            setShowMyExperience(false);
          }
        }}>
        
                    <div
          style={{
            background: 'white',
            borderRadius: '8px',
            padding: '20px',
            maxWidth: '500px',
            width: '90%',
            maxHeight: '60vh',
            overflow: 'auto'
          }}
          onClickCapture={(e) => e.stopPropagation()}>
          
                        <h3 style={{ margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            📜 Мой опыт по {icd10Code}
                        </h3>
                        {myExperienceTemplates.length === 0 ?
          <p style={{ color: '#666', textAlign: 'center', padding: '20px' }}>
                                Нет сохранённых шаблонов для этого диагноза.<br />
                                <small>Они появятся после подписания EMR с этим кодом.</small>
                            </p> :

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {myExperienceTemplates.map((t) =>
            <div
              key={t.id}
              style={{
                display: 'flex',
                alignItems: 'stretch',
                gap: '8px',
                padding: '8px',
                background: t.is_pinned ? '#fff8e1' : '#f9f9f9',
                border: t.is_pinned ? '2px solid #ffb300' : '1px solid #e0e0e0',
                borderRadius: '6px'
              }}>
              
                                        {/* Pin button */}
                                        <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  t.is_pinned ?
                  unpinTemplate(t.id) :
                  pinTemplate(t.id);
                }}
                title={t.is_pinned ? 'Открепить' : 'Закрепить (макс 3)'}
                style={{
                  padding: '4px 8px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  opacity: t.is_pinned ? 1 : 0.4,
                  color: t.is_pinned ? 'var(--accent-warning, #f59e0b)' : 'var(--text-muted, #6b7280)'
                }}>
                
                                            <Pin size={16} />
                                        </button>

                                        {/* Edit button */}
                                        <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingTemplate(t);
                  setEditText(t.treatment_text);
                }}
                title="Редактировать"
                style={{
                  padding: '4px 8px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  opacity: 0.6,
                  color: 'var(--text-muted, #6b7280)'
                }}>
                
                                            <Edit2 size={14} />
                                        </button>

                                        {/* Template content - clickable */}
                                        <button
                type="button"
                onClick={() => handleApplyMyExperience(t)}
                style={{
                  flex: 1,
                  textAlign: 'left',
                  padding: '4px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer'
                }}>
                
                                            <div style={{ fontSize: '14px', marginBottom: '4px', color: 'var(--text-primary, #f0f1f4)' }}>
                                                {t.treatment_text.substring(0, 150)}
                                                {t.treatment_text.length > 150 && '...'}
                                            </div>
                                            <div style={{ fontSize: '11px', color: 'var(--text-muted, #6b7280)', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                                                {/* Stale warning - soft, not aggressive */}
                                                {t.is_stale &&
                  <span className="badge badge--stale" style={{
                    padding: '2px 6px',
                    borderRadius: 'var(--radius-full, 9999px)',
                    fontSize: '10px',
                    background: 'var(--stale-bg, #252540)',
                    color: 'var(--stale-text, #6b7280)',
                    border: '1px solid var(--stale-border, rgba(255,255,255,0.1))'
                  }}>
                                                        Давно не использовал
                                                    </span>
                  }
                                                {/* Frequency badge - no aggressive numbers */}
                                                {t.frequency_label && !t.is_stale &&
                  <span
                    className={`badge ${t.frequency_label === 'часто' ? 'badge--frequent' : 'badge--rare'}`}
                    style={{
                      padding: '2px 6px',
                      borderRadius: 'var(--radius-full, 9999px)',
                      fontSize: '10px',
                      background: t.frequency_label === 'часто' ?
                      'var(--accent-success-muted, rgba(34, 197, 94, 0.15))' :
                      'var(--surface-input, #252540)',
                      color: t.frequency_label === 'часто' ?
                      'var(--accent-success, #22c55e)' :
                      'var(--text-muted, #6b7280)'
                    }}>
                    
                                                        {t.frequency_label === 'часто' ? 'часто' : 'редко'}
                                                    </span>
                  }
                                                <span>
                                                    {new Date(t.last_used_at).toLocaleDateString()}
                                                </span>
                                            </div>
                                        </button>
                                    </div>
            )}
                            </div>
          }
                        <button
            type="button"
            onClick={() => setShowMyExperience(false)}
            style={{
              marginTop: '16px',
              padding: '8px 16px',
              width: '100%',
              background: '#f0f0f0',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}>
            
                            Закрыть
                        </button>
                    </div>
                </div>
      }

            {/* 📋 Generic Templates Panel Modal */}
            <TreatmentTemplatesPanel
        isOpen={showTemplates}
        specialty={specialty}
        currentValue={value}
        onApply={handleApplyTemplate}
        onClose={() => setShowTemplates(false)} />
      

            {/* ✏️ Edit Template Modal */}
            {editingTemplate &&
      <div
        style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1001
        }}
        role="button"
        tabIndex={0}
        onClick={() => setEditingTemplate(null)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            setEditingTemplate(null);
          }
        }}>
        
                    <div
          style={{
            background: 'white',
            borderRadius: '8px',
            padding: '20px',
            maxWidth: '500px',
            width: '90%'
          }}
          onClickCapture={(e) => e.stopPropagation()}>
          
                        <h3 style={{ margin: '0 0 16px' }}>
                            ✏️ Редактировать шаблон
                        </h3>
                        <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            style={{
              width: '100%',
              minHeight: '150px',
              padding: '12px',
              border: '1px solid #ddd',
              borderRadius: '6px',
              fontSize: '14px',
              resize: 'vertical'
            }} />
          
                        <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                            <button
              type="button"
              onClick={async () => {
                await updateTemplate(editingTemplate.id, editText, 'replace');
                setEditingTemplate(null);
              }}
              style={{
                flex: 1,
                padding: '10px',
                background: '#fff3e0',
                border: '1px solid #ff9800',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px'
              }}>
              
                                ♻️ Заменить старый
                            </button>
                            <button
              type="button"
              onClick={async () => {
                await updateTemplate(editingTemplate.id, editText, 'save_as_new');
                setEditingTemplate(null);
              }}
              style={{
                flex: 1,
                padding: '10px',
                background: '#e8f5e9',
                border: '1px solid #4caf50',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px'
              }}>
              
                                💾 Сохранить как новый
                            </button>
                        </div>
                        <button
            type="button"
            onClick={() => setEditingTemplate(null)}
            style={{
              marginTop: '12px',
              padding: '8px 16px',
              width: '100%',
              background: '#f0f0f0',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}>
            
                            Отмена
                        </button>
                    </div>
                </div>
      }
        </EMRSection>);

}

TreatmentSection.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func,
  medications: PropTypes.arrayOf(PropTypes.object),
  onMedicationsChange: PropTypes.func,
  disabled: PropTypes.bool,
  defaultOpen: PropTypes.bool,
  specialty: PropTypes.string,
  icd10Code: PropTypes.string,
  complaints: PropTypes.string,
  suggestions: PropTypes.arrayOf(PropTypes.object),
  aiLoading: PropTypes.bool,
  onApplySuggestion: PropTypes.func,
  onDismissSuggestion: PropTypes.func,
  onRequestAI: PropTypes.func,
  doctorId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  experimentalGhostMode: PropTypes.bool,
  onTelemetry: PropTypes.func
};

export default TreatmentSection;
