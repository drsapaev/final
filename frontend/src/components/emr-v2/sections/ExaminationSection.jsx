/**
 * ExaminationSection - Осмотр с "Мой опыт"
 * 
 * ⚠️ AI - только при наличии жалоб
 * ✅ "Мой опыт" - всегда доступен
 */

import PropTypes from 'prop-types';
import { useState, useMemo, useCallback } from 'react';

import EMRSection from './EMRSection';
import EMRSmartFieldV2 from './EMRSmartFieldV2';
import ExaminationMatrix from '../../emr/ExaminationMatrix';
import { useDoctorPhrases } from '../../../hooks/useDoctorPhrases';
import { DoctorTemplatesPanel, DoctorTemplatesButton } from '../DoctorTemplatesPanel';
import { useDoctorSectionTemplates } from '../../../hooks/useDoctorSectionTemplates';
import logger from '../../../utils/logger';

/**
 * ExaminationSection Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler
 * @param {boolean} props.disabled - Read-only mode
 * @param {boolean} props.defaultOpen - Start expanded
 * @param {string} props.icd10Code - ICD-10 code for personalized templates
 * @param {string} props.complaints - Complaints text (required for AI)
 */
export function ExaminationSection({
  value = '',
  onChange,
  disabled = false,
  defaultOpen = true,
  specialty = 'general',
  icd10Code = '',
  complaints = '', // NEW: для проверки AI доступности
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
  const [showMyExperience, setShowMyExperience] = useState(false);

  // 🧠 Connect Doctor History (Personal Learning)
  const { suggestions: doctorSuggestions, loading: historyLoading } = useDoctorPhrases({
    doctorId,
    field: 'examination',
    specialty,
    currentText: value,
    config: { minQueryLength: 2 }
  });

  // Get section templates
  const {
    templates,
    loading: templatesLoading,
    hasTemplates
  } = useDoctorSectionTemplates({
    section: 'examination',
    icd10Code: icd10Code || null
  });

  // ⚠️ AI доступен только если есть жалобы
  const aiEnabled = Boolean(complaints && complaints.trim().length > 0);

  // Merge suggestions: Doctor History first, then Generic AI
  const allSuggestions = useMemo(() => {
    const historyItems = doctorSuggestions.map((s) => ({
      id: s.id,
      content: s.text,
      source: 'history', // Badge will show "История"
      confidence: 1.0
    }));

    return [...historyItems, ...suggestions];
  }, [doctorSuggestions, suggestions]);

  // Append generated text from matrix
  const handleMatrixText = (text) => {
    if (!text) return;
    const current = value || '';
    const newValue = current ? `${current} ${text}` : text;
    onChange?.(newValue, { source: 'matrix' });
  };

  // Handle AI request - only if complaints exist
  const handleRequestAI = useCallback((fieldName) => {
    if (!aiEnabled) {
      // Show info message instead of silent failure
      logger.log('[ExaminationSection] AI disabled - no complaints');
      return;
    }
    onRequestAI?.(fieldName);
  }, [aiEnabled, onRequestAI]);

  // Handle template apply
  const handleApplyTemplate = useCallback((text) => {
    if (!text) return;
    const current = value || '';
    const newValue = current.trim() ?
    `${current.trim()}\n\n${text}` :
    text;
    onChange?.(newValue);
  }, [value, onChange]);

  return (
    <EMRSection
      title="Объективный осмотр"
      icon="🔍"
      disabled={disabled}
      defaultOpen={defaultOpen}
      headerAction={
      <DoctorTemplatesButton
        onClick={() => setShowMyExperience(true)}
        disabled={disabled || templatesLoading}
        hasTemplates={hasTemplates}
        count={templates.length} />

      }>
      
            <div style={{ marginBottom: '12px' }}>
                <ExaminationMatrix
          specialty={specialty}
          isEditable={!disabled}
          onGenerateText={handleMatrixText} />
        
            </div>

            <EMRSmartFieldV2
        value={value}
        onChange={onChange}
        placeholder="Общее состояние, кожные покровы, лимфоузлы, органы и системы..."
        multiline
        rows={4}
        disabled={disabled}
        id="emr-examination"
        fieldName="examination"
        suggestions={allSuggestions}
        aiLoading={aiLoading || historyLoading}
        onApplySuggestion={onApplySuggestion}
        onDismissSuggestion={onDismissSuggestion}
        onRequestAI={aiEnabled ? handleRequestAI : null}
        showAIButton={aiEnabled}
        experimentalGhostMode={experimentalGhostMode}
        onTelemetry={onTelemetry}
        aiDisabledTooltip={!aiEnabled ? 'Для AI сначала заполните жалобы' : undefined} />
      

            {/* My Experience Panel */}
            <DoctorTemplatesPanel
        section="examination"
        icd10Code={icd10Code}
        onApply={handleApplyTemplate}
        onClose={() => setShowMyExperience(false)}
        isOpen={showMyExperience} />
      
        </EMRSection>);

}

ExaminationSection.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func,
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

export default ExaminationSection;
