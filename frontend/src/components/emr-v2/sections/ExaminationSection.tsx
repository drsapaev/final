
/**
 * ExaminationSection - Осмотр с "Мой опыт"
 * 
 * ⚠️ AI - только при наличии жалоб
 * ✅ "Мой опыт" - всегда доступен
 */

import { useState, useMemo, useCallback, useRef } from 'react';

import EMRSection from './EMRSection';
import React from 'react';
import EMRSmartFieldV2 from './EMRSmartFieldV2';
import ExaminationMatrix from './ExaminationMatrix';
import { useDoctorPhrases } from '@/hooks/useDoctorPhrases';
import { DoctorTemplatesPanel, DoctorTemplatesButton } from '../DoctorTemplatesPanel';
import { useDoctorSectionTemplates } from '@/hooks/useDoctorSectionTemplates';
import logger from '@/utils/logger';
import { useTranslation } from '@/i18n/useTranslation';


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
interface ExaminationSectionProps {
  value?: string;
  onChange?: (value: string, options?: Record<string, unknown>) => void;
  disabled?: boolean;
  defaultOpen?: boolean;
  specialty?: string;
  icd10Code?: string;
  complaints?: string;
  suggestions?: unknown[];
  aiLoading?: boolean;
  onApplySuggestion?: ((s: unknown) => void) | undefined;
  onDismissSuggestion?: ((s: unknown) => void) | undefined;
  onRequestAI?: ((text: string) => void) | undefined;
  doctorId?: string | number | null | undefined;
  experimentalGhostMode?: boolean;
  onTelemetry?: ((payload: Record<string, unknown>) => void) | undefined;
}


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
}: ExaminationSectionProps) {
  const [showMyExperience, setShowMyExperience] = useState(false);

  // 🧠 Connect Doctor History (Personal Learning)
  const { suggestions: doctorSuggestions, loading: historyLoading } = useDoctorPhrases({
    doctorId: doctorId ?? undefined,
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
    const historyItems = doctorSuggestions.map((raw: unknown) => {
      const s = raw as Record<string, unknown>;
      return {
        id: s.id,
        content: s.text,
        source: 'history', // Badge will show "История"
        confidence: 1.0
      };
    });

    return [...historyItems, ...suggestions];
  }, [doctorSuggestions, suggestions]);

  // EMREXAM-FE-001 (audit 3886, round 19): the matrix emits the FULL
  // snapshot of the currently active items on every toggle (including an
  // empty string when the last mark is removed). The old handler blindly
  // APPENDED each emission, so «norm» and «pathology» phrases accumulated
  // into contradictory saved text and toggling a mark off could not retract
  // its phrase. Now the generated block is keyed by its previous content
  // (lastMatrixTextRef) and REPLACED in place on every matrix change; an
  // empty snapshot removes the block entirely. Manual prose around the
  // block is never erased; if the doctor manually deleted the block, a new
  // selection appends a fresh block.
  const lastMatrixTextRef = useRef<string | null>(null);

  const handleMatrixText = (text: string) => {
    const current = value || '';
    const prev = lastMatrixTextRef.current;
    let next: string;

    if (prev && current.includes(prev)) {
      // Replace the previous generated block in place with the new snapshot
      // (an empty snapshot deletes the block).
      next = current.replace(prev, text);
    } else {
      // No block to replace (first generation, or the doctor manually
      // removed/edited it away): append a fresh block after the manual text.
      next = text ? (current ? `${current.trimEnd()} ${text}` : text) : current;
    }
    // Normalize whitespace artifacts left around the replaced block.
    next = next.replace(/[ \t]{2,}/g, ' ').trim();
    lastMatrixTextRef.current = text || null;
    if (next === current) return;
    onChange?.(next, { source: 'matrix' });
  };

  // Handle AI request - only if complaints exist
  const handleRequestAI = useCallback((fieldName: string) => {
    if (!aiEnabled) {
      // Show info message instead of silent failure
      logger.log('[ExaminationSection] AI disabled - no complaints');
      return;
    }
    onRequestAI?.(fieldName);
  }, [aiEnabled, onRequestAI]);

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
      
            <div style={{ marginBottom: 'var(--mac-spacing-3)' }}>
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
        onRequestAI={aiEnabled ? handleRequestAI : undefined}
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


export default ExaminationSection;
