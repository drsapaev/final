
/**
 * AnamnesisMorbiSection - Анамнез заболевания с "Мой опыт"
 * 
 * Uses Doctor History (📜) + Section Templates.
 * History = personal phrases from doctor's past records.
 */

import { useState, useMemo, useCallback } from 'react';

import EMRSection from './EMRSection';
import React from 'react';
import EMRSmartFieldV2 from './EMRSmartFieldV2';
import { useDoctorPhrases } from '@/hooks/useDoctorPhrases';
import { DoctorTemplatesPanel, DoctorTemplatesButton } from '../DoctorTemplatesPanel';
import { useDoctorSectionTemplates } from '@/hooks/useDoctorSectionTemplates';
import { useTranslation } from '@/i18n/useTranslation';


/**
 * AnamnesisMorbiSection Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler
 * @param {boolean} props.disabled - Read-only mode
 * @param {boolean} props.defaultOpen - Start expanded
 * @param {string} props.icd10Code - ICD-10 code for personalized templates
 */
interface AnamnesisMorbiSectionProps {
  value?: string;
  onChange?: ((value: string) => void) | undefined;
  disabled?: boolean;
  defaultOpen?: boolean;
  icd10Code?: string;
  onApplySuggestion?: ((s: unknown) => void) | undefined;
  onDismissSuggestion?: ((s: unknown) => void) | undefined;
  doctorId?: string | number | null | undefined;
  specialty?: string;
}


export function AnamnesisMorbiSection({
  value = '',
  onChange,
  disabled = false,
  defaultOpen = true,
  icd10Code = '',
  // History Props (NOT AI!)
  onApplySuggestion,
  onDismissSuggestion,
  doctorId,
  specialty = 'general'
}: AnamnesisMorbiSectionProps) {
  const [showMyExperience, setShowMyExperience] = useState(false);

  // 📜 Doctor History (Personal Learning) - NOT AI
  const { suggestions: doctorSuggestions, loading: historyLoading } = useDoctorPhrases({
    doctorId: doctorId ?? undefined,
    field: 'anamnesis_morbi',
    specialty,
    currentText: value,
    config: { minQueryLength: 2 }
  });

  // Get section templates (icd10 optional for anamnesis)
  const {
    templates,
    loading: templatesLoading,
    hasTemplates
  } = useDoctorSectionTemplates({
    section: 'anamnesis',
    icd10Code: icd10Code || null
  });

  // History suggestions only - no AI for this field
  const allSuggestions = useMemo(() => {
    return doctorSuggestions.map((raw: unknown) => {
      const s = raw as Record<string, unknown>;
      return {
        id: s.id,
        content: s.text,
        source: 'history', // Badge shows "📜 История"
        confidence: 1.0
      };
    });
  }, [doctorSuggestions]);

  // Handle template apply
  const handleApplyTemplate = useCallback((text: string) => {
    if (!text) return;
    const current = value || '';
    const newValue = current.trim() ?
    `${current.trim()}\n\n${text}` :
    text;
    onChange?.(newValue);
  }, [value, onChange]);

  return (
    <EMRSection
      title="Анамнез заболевания"
      icon="📖"
      disabled={disabled}
      defaultOpen={defaultOpen}
      headerAction={
      <DoctorTemplatesButton
        onClick={() => setShowMyExperience(true)}
        disabled={disabled || templatesLoading}
        hasTemplates={hasTemplates}
        count={templates.length} />

      }>
      
            <EMRSmartFieldV2
        value={value}
        onChange={onChange}
        placeholder="История текущего заболевания..."
        multiline
        rows={3}
        disabled={disabled}
        id="emr-anamnesis-morbi"
        fieldName="anamnesis_morbi"
        suggestions={allSuggestions}
        aiLoading={historyLoading}
        onApplySuggestion={onApplySuggestion}
        onDismissSuggestion={onDismissSuggestion}
        showAIButton={false} />
      

            {/* My Experience Panel */}
            <DoctorTemplatesPanel
        section="anamnesis"
        icd10Code={icd10Code}
        onApply={handleApplyTemplate}
        onClose={() => setShowMyExperience(false)}
        isOpen={showMyExperience} />
      
        </EMRSection>);

}

export default AnamnesisMorbiSection;

